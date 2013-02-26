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
from ...utils import angle_on_plane
from ...utils import copy_bone
from ...utils import strip_org, make_mechanism_name, insert_before_lr
from ...utils import get_layers


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

        # Create the control bones
        ulimb = copy_bone(self.obj, self.org_bones[0], strip_org(insert_before_lr(self.org_bones[0], ".fk")))
        flimb = copy_bone(self.obj, self.org_bones[1], strip_org(insert_before_lr(self.org_bones[1], ".fk")))
        elimb = copy_bone(self.obj, self.org_bones[2], strip_org(insert_before_lr(self.org_bones[2], ".fk")))

        # Create the end-limb mechanism bone
        elimb_mch = copy_bone(self.obj, self.org_bones[2], make_mechanism_name(strip_org(self.org_bones[2])))

        # Create the hinge bones
        if self.org_parent != None:
            hinge = copy_bone(self.obj, self.org_parent, make_mechanism_name(ulimb + ".hinge"))
            socket1 = copy_bone(self.obj, ulimb, make_mechanism_name(ulimb + ".socket1"))
            socket2 = copy_bone(self.obj, ulimb, make_mechanism_name(ulimb + ".socket2"))

        # Get edit bones
        eb = self.obj.data.edit_bones

        ulimb_e = eb[ulimb]
        flimb_e = eb[flimb]
        elimb_e = eb[elimb]
        elimb_mch_e = eb[elimb_mch]

        if self.org_parent != None:
            hinge_e = eb[hinge]
            socket1_e = eb[socket1]
            socket2_e = eb[socket2]

        # Parenting
        flimb_e.parent = ulimb_e
        elimb_e.parent = flimb_e
        
        elimb_mch_e.use_connect = False
        elimb_mch_e.parent = elimb_e

        if self.org_parent != None:
            hinge_e.use_connect = False
            socket1_e.use_connect = False
            socket2_e.use_connect = False

            ulimb_e.parent = hinge_e
            hinge_e.parent = socket2_e
            socket2_e.parent = None

        # Positioning
        if self.org_parent != None:
            center = (hinge_e.head + hinge_e.tail) / 2
            hinge_e.head = center
            socket1_e.length /= 4
            socket2_e.length /= 3

        # Object mode, get pose bones
        bpy.ops.object.mode_set(mode='OBJECT')
        pb = self.obj.pose.bones

        ulimb_p = pb[ulimb]
        flimb_p = pb[flimb]
        elimb_p = pb[elimb]
        elimb_mch_p = pb[elimb_mch]
        
        if self.org_parent != None:
            hinge_p = pb[hinge]

        if self.org_parent != None:
            socket2_p = pb[socket2]

        # Set the elbow to only bend on the x-axis.
        flimb_p.rotation_mode = 'XYZ'
        if 'X' in self.primary_rotation_axis:
            flimb_p.lock_rotation = (False, True, True)
        elif 'Y' in self.primary_rotation_axis:
            flimb_p.lock_rotation = (True, False, True)
        else:
            flimb_p.lock_rotation = (True, True, False)

        # Hinge transforms are locked, for auto-ik
        if self.org_parent != None:
            hinge_p.lock_location = True, True, True
            hinge_p.lock_rotation = True, True, True
            hinge_p.lock_rotation_w = True
            hinge_p.lock_scale = True, True, True

        # Set up custom properties
        if self.org_parent != None:
            prop = rna_idprop_ui_prop_get(ulimb_p, "isolate", create=True)
            ulimb_p["isolate"] = 0.0
            prop["soft_min"] = prop["min"] = 0.0
            prop["soft_max"] = prop["max"] = 1.0

        # Hinge constraints / drivers
        if self.org_parent != None:
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

        return [ulimb, flimb, elimb, elimb_mch]


class IKLimb:
    """ An IK limb rig, with an optional ik/fk switch.

    """
    def __init__(self, obj, bone1, bone2, bone3, pole_target_base_name, primary_rotation_axis, bend_hint, layers, ikfk_switch=False):
        """ Gather and validate data about the rig.
            Store any data or references to data that will be needed later on.
            In particular, store references to bones that will be needed, and
            store names of bones that will be needed.
            Do NOT change any data in the scene.  This is a gathering phase only.

            ikfk_switch: if True, create an ik/fk switch slider
        """
        self.obj = obj
        self.switch = ikfk_switch

        # Get the chain of 3 connected bones
        self.org_bones = [bone1, bone2, bone3]

        # Get the rig parameters
        self.pole_target_base_name = pole_target_base_name
        self.layers = layers
        self.bend_hint = bend_hint
        self.primary_rotation_axis = primary_rotation_axis

    def generate(self):
        """ Generate the rig.
            Do NOT modify any of the original bones, except for adding constraints.
            The main armature should be selected and active before this is called.

        """
        bpy.ops.object.mode_set(mode='EDIT')

        # Create the bones
        ulimb = copy_bone(self.obj, self.org_bones[0], make_mechanism_name(strip_org(insert_before_lr(self.org_bones[0], ".ik"))))
        flimb = copy_bone(self.obj, self.org_bones[1], make_mechanism_name(strip_org(insert_before_lr(self.org_bones[1], ".ik"))))

        elimb = copy_bone(self.obj, self.org_bones[2], strip_org(insert_before_lr(self.org_bones[2], ".ik")))
        pole_target_name = self.pole_target_base_name + "." + insert_before_lr(self.org_bones[0], ".ik").split(".", 1)[1]
        pole = copy_bone(self.obj, self.org_bones[0], pole_target_name)

        viselimb = copy_bone(self.obj, self.org_bones[2], "VIS-" + strip_org(insert_before_lr(self.org_bones[2], ".ik")))
        vispole = copy_bone(self.obj, self.org_bones[1], "VIS-" + strip_org(insert_before_lr(self.org_bones[0], "_pole.ik")))

        # Get edit bones
        eb = self.obj.data.edit_bones

        ulimb_e = eb[ulimb]
        flimb_e = eb[flimb]
        elimb_e = eb[elimb]
        pole_e = eb[pole]
        viselimb_e = eb[viselimb]
        vispole_e = eb[vispole]

        # Parenting
        flimb_e.parent = ulimb_e

        elimb_e.use_connect = False
        elimb_e.parent = None

        pole_e.use_connect = False

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

        # ulimb_p = pb[ulimb]  # UNUSED
        flimb_p = pb[flimb]
        elimb_p = pb[elimb]
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
        con.subtarget = elimb
        con.pole_target = self.obj
        con.pole_subtarget = pole
        con.pole_angle = pole_offset
        con.chain_count = 2

        # Constrain org bones to controls
        con = pb[self.org_bones[0]].constraints.new('COPY_TRANSFORMS')
        con.name = "ik"
        con.target = self.obj
        con.subtarget = ulimb
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
        con.subtarget = flimb
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
        con.subtarget = elimb
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

        return [ulimb, flimb, elimb, pole, vispole, viselimb]
