#====================== BEGIN GPL LICENSE BLOCK ======================
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
#======================= END GPL LICENSE BLOCK ========================

from math import pi

import bpy
from rna_prop_ui import rna_idprop_ui_prop_get
from mathutils import Vector

from ...utils import MetarigError
from ...utils import angle_on_plane, align_bone_roll
from ...utils import new_bone, copy_bone, put_bone, make_nonscaling_child
from ...utils import strip_org, make_mechanism_name, make_deformer_name, insert_before_lr
from ...utils import get_layers
from ...utils import create_widget, create_limb_widget, create_line_widget, create_sphere_widget, create_circle_widget


class FKLimb:
    def __init__(self, obj, bone1, bone2, bone3, primary_rotation_axis, layers):
        self.obj = obj

        self.org_bones = [bone1, bone2, bone3]

        # Get (optional) parent
        if self.obj.data.bones[bone1].parent is None:
            self.org_parent = None
        else:
            self.org_parent = self.obj.data.bones[bone1].parent.name

        # Get the rig parameters
        self.layers = layers
        self.primary_rotation_axis = primary_rotation_axis

    def generate(self):
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Create non-scaling parent bone
        if self.org_parent != None:
            loc = Vector(self.obj.data.edit_bones[self.org_bones[0]].head)
            parent = make_nonscaling_child(self.obj, self.org_parent, loc, "_fk")
        else:
            parent = None

        # Create the control bones
        ulimb = copy_bone(self.obj, self.org_bones[0], strip_org(insert_before_lr(self.org_bones[0], ".fk")))
        flimb = copy_bone(self.obj, self.org_bones[1], strip_org(insert_before_lr(self.org_bones[1], ".fk")))
        elimb = copy_bone(self.obj, self.org_bones[2], strip_org(insert_before_lr(self.org_bones[2], ".fk")))

        # Create the end-limb mechanism bone
        elimb_mch = copy_bone(self.obj, self.org_bones[2], make_mechanism_name(strip_org(self.org_bones[2])))

        # Create the hinge bones
        if parent != None:
            socket1 = copy_bone(self.obj, ulimb, make_mechanism_name(ulimb + ".socket1"))
            socket2 = copy_bone(self.obj, ulimb, make_mechanism_name(ulimb + ".socket2"))

        # Get edit bones
        eb = self.obj.data.edit_bones

        ulimb_e = eb[ulimb]
        flimb_e = eb[flimb]
        elimb_e = eb[elimb]
        elimb_mch_e = eb[elimb_mch]

        if parent != None:
            socket1_e = eb[socket1]
            socket2_e = eb[socket2]

        # Parenting
        flimb_e.parent = ulimb_e
        elimb_e.parent = flimb_e
        
        elimb_mch_e.use_connect = False
        elimb_mch_e.parent = elimb_e

        if parent != None:
            socket1_e.use_connect = False
            socket1_e.parent = eb[parent]
            
            socket2_e.use_connect = False
            socket2_e.parent = None
            
            ulimb_e.use_connect = False
            ulimb_e.parent = socket2_e
            

        # Positioning
        if parent != None:
            socket1_e.length /= 4
            socket2_e.length /= 3

        # Object mode, get pose bones
        bpy.ops.object.mode_set(mode='OBJECT')
        pb = self.obj.pose.bones

        ulimb_p = pb[ulimb]
        flimb_p = pb[flimb]
        elimb_p = pb[elimb]
        elimb_mch_p = pb[elimb_mch]

        if parent != None:
            socket2_p = pb[socket2]

        # Set the elbow to only bend on the x-axis.
        flimb_p.rotation_mode = 'XYZ'
        if 'X' in self.primary_rotation_axis:
            flimb_p.lock_rotation = (False, True, True)
        elif 'Y' in self.primary_rotation_axis:
            flimb_p.lock_rotation = (True, False, True)
        else:
            flimb_p.lock_rotation = (True, True, False)

        # Set up custom properties
        if parent != None:
            prop = rna_idprop_ui_prop_get(ulimb_p, "isolate", create=True)
            ulimb_p["isolate"] = 0.0
            prop["soft_min"] = prop["min"] = 0.0
            prop["soft_max"] = prop["max"] = 1.0

        # Hinge constraints / drivers
        if parent != None:
            con = socket2_p.constraints.new('COPY_LOCATION')
            con.name = "copy_location"
            con.target = self.obj
            con.subtarget = socket1

            con = socket2_p.constraints.new('COPY_TRANSFORMS')
            con.name = "isolate_off"
            con.target = self.obj
            con.subtarget = socket1

            # Driver
            fcurve = con.driver_add("influence")
            driver = fcurve.driver
            var = driver.variables.new()
            driver.type = 'AVERAGE'
            var.name = "var"
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = self.obj
            var.targets[0].data_path = ulimb_p.path_from_id() + '["isolate"]'
            mod = fcurve.modifiers[0]
            mod.poly_order = 1
            mod.coefficients[0] = 1.0
            mod.coefficients[1] = -1.0

        # Constrain org bones to controls
        con = pb[self.org_bones[0]].constraints.new('COPY_TRANSFORMS')
        con.name = "fk"
        con.target = self.obj
        con.subtarget = ulimb

        con = pb[self.org_bones[1]].constraints.new('COPY_TRANSFORMS')
        con.name = "fk"
        con.target = self.obj
        con.subtarget = flimb

        con = pb[self.org_bones[2]].constraints.new('COPY_TRANSFORMS')
        con.name = "fk"
        con.target = self.obj
        con.subtarget = elimb_mch

        # Set layers if specified
        if self.layers:
            ulimb_p.bone.layers = self.layers
            flimb_p.bone.layers = self.layers
            elimb_p.bone.layers = self.layers
        
        # Create control widgets
        create_limb_widget(self.obj, ulimb)
        create_limb_widget(self.obj, flimb)

        ob = create_widget(self.obj, elimb)
        if ob != None:
            verts = [(0.7, 1.5, 0.0), (0.7, -0.25, 0.0), (-0.7, -0.25, 0.0), (-0.7, 1.5, 0.0), (0.7, 0.723, 0.0), (-0.7, 0.723, 0.0), (0.7, 0.0, 0.0), (-0.7, 0.0, 0.0)]
            edges = [(1, 2), (0, 3), (0, 4), (3, 5), (4, 6), (1, 6), (5, 7), (2, 7)]
            mesh = ob.data
            mesh.from_pydata(verts, edges, [])
            mesh.update()

            mod = ob.modifiers.new("subsurf", 'SUBSURF')
            mod.levels = 2

        return [ulimb, flimb, elimb, elimb_mch]


class IKLimb:
    """ An IK limb rig, with an optional ik/fk switch.

    """
    def __init__(self, obj, bone1, bone2, bone3, pole_target_base_name, primary_rotation_axis, bend_hint, layers, ikfk_switch=False):
        self.obj = obj
        self.switch = ikfk_switch

        # Get the chain of 3 connected bones
        self.org_bones = [bone1, bone2, bone3]

        # Get (optional) parent
        if self.obj.data.bones[bone1].parent is None:
            self.org_parent = None
        else:
            self.org_parent = self.obj.data.bones[bone1].parent.name

        # Get the rig parameters
        self.pole_target_base_name = pole_target_base_name
        self.layers = layers
        self.bend_hint = bend_hint
        self.primary_rotation_axis = primary_rotation_axis

    def generate(self):
        bpy.ops.object.mode_set(mode='EDIT')

        # Create non-scaling parent bone
        if self.org_parent != None:
            loc = Vector(self.obj.data.edit_bones[self.org_bones[0]].head)
            parent = make_nonscaling_child(self.obj, self.org_parent, loc, "_ik")
        else:
            parent = None

        # Create the bones
        ulimb = copy_bone(self.obj, self.org_bones[0], make_mechanism_name(strip_org(insert_before_lr(self.org_bones[0], ".ik"))))
        flimb = copy_bone(self.obj, self.org_bones[1], make_mechanism_name(strip_org(insert_before_lr(self.org_bones[1], ".ik"))))
        elimb = copy_bone(self.obj, self.org_bones[2], strip_org(insert_before_lr(self.org_bones[2], ".ik")))
        elimb_mch = copy_bone(self.obj, self.org_bones[2], make_mechanism_name(strip_org(self.org_bones[2])))
        
        ulimb_str = copy_bone(self.obj, self.org_bones[0], make_mechanism_name(strip_org(insert_before_lr(self.org_bones[0], ".stretch.ik"))))
        flimb_str = copy_bone(self.obj, self.org_bones[1], make_mechanism_name(strip_org(insert_before_lr(self.org_bones[1], ".stretch.ik"))))

        pole_target_name = self.pole_target_base_name + "." + insert_before_lr(self.org_bones[0], ".ik").split(".", 1)[1]
        pole = copy_bone(self.obj, self.org_bones[0], pole_target_name)

        viselimb = copy_bone(self.obj, self.org_bones[2], "VIS-" + strip_org(insert_before_lr(self.org_bones[2], ".ik")))
        vispole = copy_bone(self.obj, self.org_bones[1], "VIS-" + strip_org(insert_before_lr(self.org_bones[0], "_pole.ik")))

        # Get edit bones
        eb = self.obj.data.edit_bones

        if parent != None:
            parent_e = eb[parent]
        ulimb_e = eb[ulimb]
        flimb_e = eb[flimb]
        elimb_e = eb[elimb]
        elimb_mch_e = eb[elimb_mch]
        ulimb_str_e = eb[ulimb_str]
        flimb_str_e = eb[flimb_str]
        pole_e = eb[pole]
        viselimb_e = eb[viselimb]
        vispole_e = eb[vispole]

        # Parenting
        ulimb_e.use_connect = False
        if parent != None:
            ulimb_e.parent = parent_e
        
        flimb_e.parent = ulimb_e

        elimb_e.use_connect = False
        elimb_e.parent = None
        
        elimb_mch_e.use_connect = False
        elimb_mch_e.parent = elimb_e
        
        ulimb_str_e.use_connect = False
        ulimb_str_e.parent = ulimb_e.parent
        
        flimb_str_e.use_connect = False
        flimb_str_e.parent = ulimb_e.parent

        pole_e.use_connect = False
        if parent != None:
            pole_e.parent = parent_e

        viselimb_e.use_connect = False
        viselimb_e.parent = None

        vispole_e.use_connect = False
        vispole_e.parent = None

        # Misc
        elimb_e.use_local_location = False

        viselimb_e.hide_select = True
        vispole_e.hide_select = True

        # Positioning
        v1 = flimb_e.tail - ulimb_e.head
        if 'X' in self.primary_rotation_axis or 'Y' in self.primary_rotation_axis:
            v2 = v1.cross(flimb_e.x_axis)
            if (v2 * flimb_e.z_axis) > 0.0:
                v2 *= -1.0
        else:
            v2 = v1.cross(flimb_e.z_axis)
            if (v2 * flimb_e.x_axis) < 0.0:
                v2 *= -1.0
        v2.normalize()
        v2 *= v1.length

        if '-' in self.primary_rotation_axis:
            v2 *= -1

        pole_e.head = flimb_e.head + v2
        pole_e.tail = pole_e.head + (Vector((0, 1, 0)) * (v1.length / 8))
        pole_e.roll = 0.0

        viselimb_e.tail = viselimb_e.head + Vector((0, 0, v1.length / 32))
        vispole_e.tail = vispole_e.head + Vector((0, 0, v1.length / 32))

        # Determine the pole offset value
        plane = (flimb_e.tail - ulimb_e.head).normalized()
        vec1 = ulimb_e.x_axis.normalized()
        vec2 = (pole_e.head - ulimb_e.head).normalized()
        pole_offset = angle_on_plane(plane, vec1, vec2)

        # Object mode, get pose bones
        bpy.ops.object.mode_set(mode='OBJECT')
        pb = self.obj.pose.bones

        ulimb_p = pb[ulimb]
        flimb_p = pb[flimb]
        elimb_p = pb[elimb]
        ulimb_str_p = pb[ulimb_str]
        flimb_str_p = pb[flimb_str]
        pole_p = pb[pole]
        viselimb_p = pb[viselimb]
        vispole_p = pb[vispole]

        # Set the elbow to only bend on the primary axis
        if 'X' in self.primary_rotation_axis:
            flimb_p.lock_ik_y = True
            flimb_p.lock_ik_z = True
        elif 'Y' in self.primary_rotation_axis:
            flimb_p.lock_ik_x = True
            flimb_p.lock_ik_z = True
        else:
            flimb_p.lock_ik_x = True
            flimb_p.lock_ik_y = True
        
        # Limb stretches
        ulimb_p.ik_stretch = 0.0001
        flimb_p.ik_stretch = 0.0001

        # Pole target only translates
        pole_p.lock_location = False, False, False
        pole_p.lock_rotation = True, True, True
        pole_p.lock_rotation_w = True
        pole_p.lock_scale = True, True, True

        # Set up custom properties
        if self.switch is True:
            prop = rna_idprop_ui_prop_get(elimb_p, "ikfk_switch", create=True)
            elimb_p["ikfk_switch"] = 0.0
            prop["soft_min"] = prop["min"] = 0.0
            prop["soft_max"] = prop["max"] = 1.0

        # Bend direction hint
        if self.bend_hint:
            con = flimb_p.constraints.new('LIMIT_ROTATION')
            con.name = "bend_hint"
            con.owner_space = 'LOCAL'
            if self.primary_rotation_axis == 'X':
                con.use_limit_x = True
                con.min_x = pi / 10
                con.max_x = pi / 10
            elif self.primary_rotation_axis == '-X':
                con.use_limit_x = True
                con.min_x = -pi / 10
                con.max_x = -pi / 10
            elif self.primary_rotation_axis == 'Y':
                con.use_limit_y = True
                con.min_y = pi / 10
                con.max_y = pi / 10
            elif self.primary_rotation_axis == '-Y':
                con.use_limit_y = True
                con.min_y = -pi / 10
                con.max_y = -pi / 10
            elif self.primary_rotation_axis == 'Z':
                con.use_limit_z = True
                con.min_z = pi / 10
                con.max_z = pi / 10
            elif self.primary_rotation_axis == '-Z':
                con.use_limit_z = True
                con.min_z = -pi / 10
                con.max_z = -pi / 10

        # IK Constraint
        con = flimb_p.constraints.new('IK')
        con.name = "ik"
        con.target = self.obj
        con.subtarget = elimb_mch
        con.pole_target = self.obj
        con.pole_subtarget = pole
        con.pole_angle = pole_offset
        con.chain_count = 2
        
        # Stretch bone constraints
        con = ulimb_str_p.constraints.new('COPY_TRANSFORMS')
        con.name = "anchor"
        con.target = self.obj
        con.subtarget = ulimb
        con = ulimb_str_p.constraints.new('MAINTAIN_VOLUME')
        con.name = "stretch"
        
        con = flimb_str_p.constraints.new('COPY_TRANSFORMS')
        con.name = "anchor"
        con.target = self.obj
        con.subtarget = flimb
        con = flimb_str_p.constraints.new('MAINTAIN_VOLUME')
        con.name = "stretch"
        
        # Constrain org bones
        con = pb[self.org_bones[0]].constraints.new('COPY_TRANSFORMS')
        con.name = "ik"
        con.target = self.obj
        con.subtarget = ulimb_str
        if self.switch is True:
            # IK/FK switch driver
            fcurve = con.driver_add("influence")
            driver = fcurve.driver
            var = driver.variables.new()
            driver.type = 'AVERAGE'
            var.name = "var"
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = self.obj
            var.targets[0].data_path = elimb_p.path_from_id() + '["ikfk_switch"]'

        con = pb[self.org_bones[1]].constraints.new('COPY_TRANSFORMS')
        con.name = "ik"
        con.target = self.obj
        con.subtarget = flimb_str
        if self.switch is True:
            # IK/FK switch driver
            fcurve = con.driver_add("influence")
            driver = fcurve.driver
            var = driver.variables.new()
            driver.type = 'AVERAGE'
            var.name = "var"
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = self.obj
            var.targets[0].data_path = elimb_p.path_from_id() + '["ikfk_switch"]'

        con = pb[self.org_bones[2]].constraints.new('COPY_TRANSFORMS')
        con.name = "ik"
        con.target = self.obj
        con.subtarget = elimb_mch
        if self.switch is True:
            # IK/FK switch driver
            fcurve = con.driver_add("influence")
            driver = fcurve.driver
            var = driver.variables.new()
            driver.type = 'AVERAGE'
            var.name = "var"
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = self.obj
            var.targets[0].data_path = elimb_p.path_from_id() + '["ikfk_switch"]'

        # VIS limb-end constraints
        con = viselimb_p.constraints.new('COPY_LOCATION')
        con.name = "copy_loc"
        con.target = self.obj
        con.subtarget = self.org_bones[2]

        con = viselimb_p.constraints.new('STRETCH_TO')
        con.name = "stretch_to"
        con.target = self.obj
        con.subtarget = elimb
        con.volume = 'NO_VOLUME'
        con.rest_length = viselimb_p.length

        # VIS pole constraints
        con = vispole_p.constraints.new('COPY_LOCATION')
        con.name = "copy_loc"
        con.target = self.obj
        con.subtarget = self.org_bones[1]

        con = vispole_p.constraints.new('STRETCH_TO')
        con.name = "stretch_to"
        con.target = self.obj
        con.subtarget = pole
        con.volume = 'NO_VOLUME'
        con.rest_length = vispole_p.length

        # Set layers if specified
        if self.layers:
            elimb_p.bone.layers = self.layers
            pole_p.bone.layers = self.layers
            viselimb_p.bone.layers = self.layers
            vispole_p.bone.layers = self.layers

        # Create widgets        
        create_line_widget(self.obj, vispole)
        create_line_widget(self.obj, viselimb)
        create_sphere_widget(self.obj, pole)
        
        ob = create_widget(self.obj, elimb)
        if ob != None:
            verts = [(0.7, 1.5, 0.0), (0.7, -0.25, 0.0), (-0.7, -0.25, 0.0), (-0.7, 1.5, 0.0), (0.7, 0.723, 0.0), (-0.7, 0.723, 0.0), (0.7, 0.0, 0.0), (-0.7, 0.0, 0.0)]
            edges = [(1, 2), (0, 3), (0, 4), (3, 5), (4, 6), (1, 6), (5, 7), (2, 7)]
            mesh = ob.data
            mesh.from_pydata(verts, edges, [])
            mesh.update()

            mod = ob.modifiers.new("subsurf", 'SUBSURF')
            mod.levels = 2

        return [ulimb, flimb, elimb, elimb_mch, pole, vispole, viselimb]


class RubberHoseLimb:
    def __init__(self, obj, bone1, bone2, bone3, use_complex_limb, junc_base_name, layers):
        self.obj = obj

        # Get the chain of 3 connected bones
        self.org_bones = [bone1, bone2, bone3]

        # Get (optional) parent
        if self.obj.data.bones[bone1].parent is None:
            self.org_parent = None
        else:
            self.org_parent = self.obj.data.bones[bone1].parent.name

        # Get rig parameters
        self.layers = layers
        self.use_complex_limb = use_complex_limb
        self.junc_base_name = junc_base_name

    def generate(self):
        bpy.ops.object.mode_set(mode='EDIT')

        # Create non-scaling parent bone
        if self.org_parent != None:
            loc = Vector(self.obj.data.edit_bones[self.org_bones[0]].head)
            parent = make_nonscaling_child(self.obj, self.org_parent, loc, "_rh")
        else:
            parent = None

        if not self.use_complex_limb:
            # Simple rig
            
            # Create bones
            ulimb = copy_bone(self.obj, self.org_bones[0], make_deformer_name(strip_org(self.org_bones[0])))
            flimb = copy_bone(self.obj, self.org_bones[1], make_deformer_name(strip_org(self.org_bones[1])))
            elimb = copy_bone(self.obj, self.org_bones[2], make_deformer_name(strip_org(self.org_bones[2])))

            # Get edit bones
            eb = self.obj.data.edit_bones

            ulimb_e = eb[ulimb]
            flimb_e = eb[flimb]
            elimb_e = eb[elimb]

            # Parenting
            elimb_e.parent = flimb_e
            elimb_e.use_connect = True
            
            flimb_e.parent = ulimb_e
            flimb_e.use_connect = True
                
            if parent != None:
                elimb_e.use_connect = False
                ulimb_e.parent = eb[parent]
            
            # Object mode, get pose bones
            bpy.ops.object.mode_set(mode='OBJECT')
            pb = self.obj.pose.bones

            ulimb_p = pb[ulimb]
            flimb_p = pb[flimb]
            elimb_p = pb[elimb]

            # Constrain def bones to org bones
            con = ulimb_p.constraints.new('COPY_TRANSFORMS')
            con.name = "def"
            con.target = self.obj
            con.subtarget = self.org_bones[0]

            con = flimb_p.constraints.new('COPY_TRANSFORMS')
            con.name = "def"
            con.target = self.obj
            con.subtarget = self.org_bones[1]

            con = elimb_p.constraints.new('COPY_TRANSFORMS')
            con.name = "def"
            con.target = self.obj
            con.subtarget = self.org_bones[2]
        else:
            # Complex rig
            
            # Create bones
            ulimb1 = copy_bone(self.obj, self.org_bones[0], make_deformer_name(strip_org(insert_before_lr(self.org_bones[0], ".01"))))
            ulimb2 = copy_bone(self.obj, self.org_bones[0], make_deformer_name(strip_org(insert_before_lr(self.org_bones[0], ".02"))))
            flimb1 = copy_bone(self.obj, self.org_bones[1], make_deformer_name(strip_org(insert_before_lr(self.org_bones[1], ".01"))))
            flimb2 = copy_bone(self.obj, self.org_bones[1], make_deformer_name(strip_org(insert_before_lr(self.org_bones[1], ".02"))))
            elimb = copy_bone(self.obj, self.org_bones[2], make_deformer_name(strip_org(self.org_bones[2])))

            junc = copy_bone(self.obj, self.org_bones[1], make_mechanism_name(strip_org(insert_before_lr(self.org_bones[1], ".junc"))))
            
            uhose = new_bone(self.obj, strip_org(insert_before_lr(self.org_bones[0], "_hose")))
            lr = self.org_bones[0].split(".", 1)  # Get the .R or .L off the end of the name if it exists
            if len(lr) == 1:
                lr = ""
            else:
                lr = lr[1]
            jhose = new_bone(self.obj, self.junc_base_name + "_hose." + lr)
            fhose = new_bone(self.obj, strip_org(insert_before_lr(self.org_bones[1], "_hose")))
        
            # Get edit bones
            eb = self.obj.data.edit_bones

            ulimb1_e = eb[ulimb1]
            ulimb2_e = eb[ulimb2]
            flimb1_e = eb[flimb1]
            flimb2_e = eb[flimb2]
            elimb_e = eb[elimb]
            
            junc_e = eb[junc]
            
            uhose_e = eb[uhose]
            jhose_e = eb[jhose]
            fhose_e = eb[fhose]
        
            # Parenting
            if parent != None:
                ulimb1_e.use_connect = False
                ulimb1_e.parent = eb[parent]
            
            ulimb2_e.use_connect = False
            ulimb2_e.parent = eb[self.org_bones[0]]
            
            flimb1_e.use_connect = True
            flimb1_e.parent = ulimb2_e
            
            flimb2_e.use_connect = False
            flimb2_e.parent = eb[self.org_bones[1]]
            
            elimb_e.use_connect = False
            elimb_e.parent = eb[self.org_bones[2]]
            
            junc_e.use_connect = False
            junc_e.parent = eb[self.org_bones[0]]
            
            uhose_e.use_connect = False
            uhose_e.parent = eb[self.org_bones[0]]
            
            jhose_e.use_connect = False
            jhose_e.parent = junc_e
            
            fhose_e.use_connect = False
            fhose_e.parent = eb[self.org_bones[1]]
            
            # Positioning
            ulimb1_e.length *= 0.5
            ulimb2_e.head = Vector(ulimb1_e.tail)
            flimb1_e.length *= 0.5
            flimb2_e.head = Vector(flimb1_e.tail)
            align_bone_roll(self.obj, flimb2, elimb)
            
            junc_e.length *= 0.2
            
            put_bone(self.obj, uhose, Vector(ulimb1_e.tail))
            put_bone(self.obj, jhose, Vector(ulimb2_e.tail))
            put_bone(self.obj, fhose, Vector(flimb1_e.tail))
            
            uhose_e.length = 0.05
            jhose_e.length = 0.05
            fhose_e.length = 0.05
            
            # Object mode, get pose bones
            bpy.ops.object.mode_set(mode='OBJECT')
            pb = self.obj.pose.bones
            
            ulimb1_p = pb[ulimb1]
            ulimb2_p = pb[ulimb2]
            flimb1_p = pb[flimb1]
            flimb2_p = pb[flimb2]
            elimb_p = pb[elimb]
            
            junc_p = pb[junc]
            
            uhose_p = pb[uhose]
            jhose_p = pb[jhose]
            fhose_p = pb[fhose]
            
            # B-bone settings
            ulimb2_p.bone.bbone_segments = 16
            ulimb2_p.bone.bbone_in = 0.0
            ulimb2_p.bone.bbone_out = 1.0
            
            flimb1_p.bone.bbone_segments = 16
            flimb1_p.bone.bbone_in = 1.0
            flimb1_p.bone.bbone_out = 0.0
            
            # Custom properties
            prop = rna_idprop_ui_prop_get(jhose_p, "smooth_bend", create=True)
            jhose_p["smooth_bend"] = 0.0
            prop["soft_min"] = prop["min"] = 0.0
            prop["soft_max"] = prop["max"] = 1.0

            # Drivers
            fcurve = ulimb2_p.bone.driver_add("bbone_out")
            driver = fcurve.driver
            var = driver.variables.new()
            driver.type = 'AVERAGE'
            var.name = "var"
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = self.obj
            var.targets[0].data_path = jhose_p.path_from_id() + '["smooth_bend"]'
            
            fcurve = flimb1_p.bone.driver_add("bbone_in")
            driver = fcurve.driver
            var = driver.variables.new()
            driver.type = 'AVERAGE'
            var.name = "var"
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = self.obj
            var.targets[0].data_path = jhose_p.path_from_id() + '["smooth_bend"]'
            
            # Constraints
            con = ulimb1_p.constraints.new('COPY_SCALE')
            con.name = "anchor"
            con.target = self.obj
            con.subtarget = self.org_bones[0]
            con = ulimb1_p.constraints.new('DAMPED_TRACK')
            con.name = "track"
            con.target = self.obj
            con.subtarget = uhose
            con = ulimb1_p.constraints.new('STRETCH_TO')
            con.name = "track"
            con.target = self.obj
            con.subtarget = uhose
            con.volume = 'NO_VOLUME'
            
            con = ulimb2_p.constraints.new('COPY_LOCATION')
            con.name = "anchor"
            con.target = self.obj
            con.subtarget = uhose
            con = ulimb2_p.constraints.new('DAMPED_TRACK')
            con.name = "track"
            con.target = self.obj
            con.subtarget = jhose
            con = ulimb2_p.constraints.new('STRETCH_TO')
            con.name = "track"
            con.target = self.obj
            con.subtarget = jhose
            con.volume = 'NO_VOLUME'
            
            con = flimb1_p.constraints.new('COPY_TRANSFORMS')
            con.name = "anchor"
            con.target = self.obj
            con.subtarget = self.org_bones[1]
            con = flimb1_p.constraints.new('COPY_LOCATION')
            con.name = "anchor"
            con.target = self.obj
            con.subtarget = jhose
            con = flimb1_p.constraints.new('DAMPED_TRACK')
            con.name = "track"
            con.target = self.obj
            con.subtarget = fhose
            con = flimb1_p.constraints.new('STRETCH_TO')
            con.name = "track"
            con.target = self.obj
            con.subtarget = fhose
            con.volume = 'NO_VOLUME'
            
            con = flimb2_p.constraints.new('COPY_LOCATION')
            con.name = "anchor"
            con.target = self.obj
            con.subtarget = fhose
            con = flimb2_p.constraints.new('COPY_ROTATION')
            con.name = "twist"
            con.target = self.obj
            con.subtarget = elimb
            con = flimb2_p.constraints.new('DAMPED_TRACK')
            con.name = "track"
            con.target = self.obj
            con.subtarget = self.org_bones[2]
            con = flimb2_p.constraints.new('STRETCH_TO')
            con.name = "track"
            con.target = self.obj
            con.subtarget = self.org_bones[2]
            con.volume = 'NO_VOLUME'
            
            con = junc_p.constraints.new('COPY_TRANSFORMS')
            con.name = "bend"
            con.target = self.obj
            con.subtarget = self.org_bones[1]
            con.influence = 0.5
            
            # Layers
            if self.layers:
                uhose_p.bone.layers = self.layers
                jhose_p.bone.layers = self.layers
                fhose_p.bone.layers = self.layers
            else:
                layers = list(pb[self.org_bones[0]].bone.layers)
                uhose_p.bone.layers = layers
                jhose_p.bone.layers = layers
                fhose_p.bone.layers = layers
            
            # Create widgets
            create_sphere_widget(self.obj, uhose)
            create_sphere_widget(self.obj, jhose)
            create_sphere_widget(self.obj, fhose)
            
            
            
