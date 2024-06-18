# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Optiloops",
    "author": "Vilem Duha",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Mesh > Mesh Tools panel > Optimize loops",
    "description": "Optimize meshes by removing loops with angle threshold",
    "warning": "",
    "wiki_url": "",
    "category": "Add Mesh",
}

import bpy, bmesh

from bpy.props import (
    IntProperty,
    BoolProperty,
    BoolVectorProperty,
    FloatProperty,
    FloatVectorProperty,
)


def get_loop(bm, e):
    checkverts = e.verts[:]
    checkedverts = []
    loop_edges = [e]
    while len(checkverts) > 0:
        v = checkverts.pop()
        checkedverts.append(v)
        if len(v.link_edges) == 4:
            for e in v.link_edges:
                if e in loop_edges:
                    estart = e
            for e in v.link_edges:
                isneighbour = False
                for f in e.link_faces:
                    if f in estart.link_faces:
                        isneighbour = True
                if not isneighbour:
                    loop_edges.append(e)
                    for v in e.verts:
                        if v not in checkedverts and v not in checkverts:
                            checkverts.append(v)
    return loop_edges


def get_neighbours(loops):
    for l in loops:
        l.neighbours = []
    for l in loops:
        e = l.edges[0]
        neighbours = 0
        for f in e.link_faces:
            if len(f.verts) == 4:
                for e1 in f.edges:
                    if e1 != e:
                        do = True
                        for v in e1.verts:  # check it's the parallel edge...
                            if v in e.verts:
                                do = False
                        if do:
                            for l1 in loops:
                                if l1 != l and e1 in l1.edges:
                                    neighbours += 1
                                    if l1 not in l.neighbours:
                                        l.neighbours.append(l1)
                                        l1.neighbours.append(l)


class edgeloop:
    edges = []
    neighbours = []


def loop_closed(es):
    closed = True
    for e in es:
        for v in e.verts:
            ec = 0
            for e1 in v.link_edges:
                if e1 in es:
                    ec += 1
            if ec == 1:
                closed = False
                return False
    return True


def check_angles(edges, angle_threshold):
    for e in edges:
        if len(e.link_faces) != 2:
            return False
        # print(len(e.link_faces))
        a = e.calc_face_angle()
        if a > angle_threshold:
            return False
    return True


def skiploop(result_loops, final_loops, skip_loops, lstart):
    final_loops.append(lstart)
    last_neighbour = None
    checkneighbours = lstart.neighbours[:]
    checked = []
    while len(checkneighbours) > 0:
        neighbour = checkneighbours.pop()
        checked.append(neighbour)
        skip_loops.append(neighbour)
        for n in neighbour.neighbours:
            if n not in final_loops and n not in checked:
                final_loops.append(n)
                checked.append(n)
                for n1 in n.neighbours:
                    checkneighbours.append(n1)

                    if n1 not in skip_loops and n1 not in final_loops:
                        skip_loops.append(n1)
                    checked.append(n1)


def optiloops(self, context):
    angle_threshold = self.angle_threshold / 180 * 3.1415926

    ob = bpy.context.active_object

    bpy.ops.object.mode_set(mode="EDIT")
    # TODO: for iterations to work, we need to reconstruct selection after the operation.
    # for main_iteration in range(0,self.iterations):
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type="EDGE")

    bm = bmesh.from_edit_mesh(ob.data)

    checkedges = []  # bm.edges[:]
    bpy.ops.mesh.loop_multi_select(ring=False)
    for e in bm.edges:
        if e.select:
            checkedges.append(e)
    if len(checkedges) == 0:
        checkedges = bm.edges[:]
    resultedges = []
    result_loops = []
    shape_loop_edges = []
    bpy.ops.mesh.select_all(action="DESELECT")
    i = 0

    attr_bevel = bm.edges.layers.float.get("bevel_weight_edge")
    attr_crease = bm.edges.layers.float.get("crease_edge")
    while len(checkedges) > 0:

        es = get_loop(bm, checkedges[0])

        for e in es:
            if e in checkedges:
                checkedges.remove(e)

        thresok = True
        if len(es) == 0:
            thresok = False

        if thresok:  # only manifold
            for e in es:
                if len(e.link_faces) < 2:
                    thresok = False
                if e.seam and self.keep_seams:
                    thresok = False
                if (attr_bevel and self.keep_bevels and e[attr_bevel] > 0.0) or (
                    attr_crease and self.keep_creases and e[attr_crease] > 0.0
                ):
                    thresok = False

        if thresok:  # first level angle check
            thresok = check_angles(es, angle_threshold)

        if thresok and self.only_closed:  # only closed check
            thresok = loop_closed(es)

        if thresok:  # append results
            resultedges.extend(es)
            loop = edgeloop()
            loop.edges = es

            result_loops.append(loop)
            # if i == 1:
            #   print(thresok)
            #  fal
        for e in es:
            e.select = False

        i += 1

    get_neighbours(result_loops)

    if self.keep_subsurf_influencing_loops:
        # check for neighbouring loops if they aren't in the cleanup group which means they are where borders start.
        remove_loops = []
        for l in result_loops:
            if len(l.neighbours) < 2:
                remove_loops.append(l)
        for l in remove_loops:
            result_loops.remove(l)
        get_neighbours(result_loops)

    if not self.finish_dissolve:
        for l in result_loops:
            for e in l.edges:
                e.select = True
    else:
        while len(result_loops) > 0:
            final_loops = []
            # while len(result_loops)>0:
            skip_loops = []

            for l in result_loops:
                if len(l.neighbours) == 1 and l.neighbours[0] not in final_loops:
                    skiploop(result_loops, final_loops, skip_loops, l)

                if len(l.neighbours) == 0:
                    final_loops.append(l)
            if len(skip_loops) + len(final_loops) < len(result_loops):
                for l in result_loops:
                    if l not in skip_loops and l not in final_loops:
                        skiploop(result_loops, final_loops, skip_loops, l)
                #    if l not in skip_loops and l not in final_loops and # nothing was done this round

            for l in final_loops:
                for e in l.edges:
                    e.select = True
                    # fal
            bpy.ops.mesh.dissolve_edges()
            result_loops = []

            for l in skip_loops:

                filter = False
                for e in l.edges:
                    if e not in bm.edges:
                        filter = True
                        continue
                if not filter:
                    if check_angles(l.edges, angle_threshold):
                        result_loops.append(l)

            get_neighbours(result_loops)
        # make things iterative here


# def main(context):
#     for ob in context.scene.objects:
#         print(ob)


class OptiloopsOperator(bpy.types.Operator):
    """Reduces mesh geometry while keeping loops"""

    bl_idname = "mesh.optiloops"
    bl_label = "Optimize loops"
    bl_options = {"REGISTER", "UNDO"}

    # iterations = IntProperty(
    #     name="Iterations",
    #     description="Number of iterations. Usefull only when Deleting is active",
    #     min=1, max=10,
    #     default=1,
    # )

    angle_threshold: FloatProperty(
        name="Max angle",
        description="loops containing only lower angles will be removed",
        min=0.01,
        max=180.0,
        default=5.0,
    )

    only_closed: BoolProperty(
        name="Remove only closed loops",
        default=False,
    )
    keep_subsurf_influencing_loops: BoolProperty(
        name="Keep loops defining subsurf creases",
        default=False,
    )

    keep_seams: BoolProperty(
        name="Keep uv seams",
        description="keep uv seams loops intact",
        default=True,
    )
    keep_bevels: BoolProperty(
        name="Keep bevels",
        description="keep bevels intact",
        default=True,
    )
    keep_creases: BoolProperty(
        name="Keep creases",
        description="keep creases intact",
        default=True,
    )

    finish_dissolve: BoolProperty(
        name="Delete loop candidates",
        description="If disabled, loops will only be selected",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        optiloops(self, context)
        return {"FINISHED"}


def optiloops_menu(self, context):
    layout = self.layout
    layout.operator("mesh.optiloops")


# Regustratuib


def register():
    bpy.utils.register_class(OptiloopsOperator)
    bpy.types.VIEW3D_MT_edit_mesh_clean.append(optiloops_menu)
    bpy.types.VIEW3D_MT_edit_mesh_delete.append(optiloops_menu)


def unregister():
    bpy.utils.unregister_class(OptiloopsOperator)
    bpy.types.VIEW3D_MT_edit_mesh_clean.remove(optiloops_menu)
    bpy.types.VIEW3D_MT_edit_mesh_delete.remove(optiloops_menu)


if __name__ == "__main__":
    register()
