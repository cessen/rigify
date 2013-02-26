import bpy
from rna_prop_ui import rna_idprop_ui_prop_get

from ...utils import MetarigError
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
