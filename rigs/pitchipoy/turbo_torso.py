import bpy
from mathutils import Vector
from ...utils import copy_bone, flip_bone, put_bone
from ...utils import strip_org, make_deformer_name, connected_children_names 
from ...utils import create_circle_widget, create_sphere_widget, create_widget
from ...utils import MetarigError, make_mechanism_name, create_cube_widget
from rna_prop_ui import rna_idprop_ui_prop_get

script = """
controls    = [%s]
head_name   = '%s'
neck_name   = '%s'
pb          = bpy.data.objects['%s'].pose.bones
torso_name  = '%s'

for name in controls:
    if is_selected( name ):
        layout.prop( pb[ torso_name ], '["%s"]', slider = True )
        layout.prop( pb[ torso_name ], '["%s"]', slider = True )
        break
"""

class Rig:
    
    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)
        self.params = params
        
        if params.tweak_extra_layers:
            self.tweak_layers = list(params.tweak_layers)
        else:
            self.tweak_layers = None
        
        # TODO Test predefined rig structure and naming
        if len(self.org_bones) <= 4:
            raise MetarigError(
                "RIGIFY ERROR: invalid rig structure" % (strip_org(bone_name))
            )            


    def create_torso( self ):
        """ Create the torso control bone """

        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
            
        org_name  = self.org_bones[0]
        
        torso_name  = self.params.torso_name
        ctrl_bone   = copy_bone(self.obj, org_name, torso_name)
        ctrl_bone_e = eb[ctrl_bone]
        
        v1    = ctrl_bone_e.head
        v2    = ctrl_bone_e.tail
        v_avg = ( v1 + v2 ) / 2
        ctrl_bone_e.head[:] = v_avg
        
        tail_vec = Vector((0, 0.25, 0)) * self.obj.matrix_world
        ctrl_bone_e.tail[:] = ctrl_bone_e.head + tail_vec
        
        return { 'ctrl' : ctrl_bone }


    def create_hips( self ):
        """ Create the hip bones """
        
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        hip_org_name   = org_bones[0]
        hip_org_bone_e = eb[hip_org_name]
        ctrl_name      = strip_org(hip_org_name)
        
        # Create ctrl
        ctrl_bone   = copy_bone(self.obj, hip_org_name, ctrl_name )
        ctrl_bone_e = eb[ctrl_bone]
        
        # Flip the hips' direction to create a more natural pivot for rotation
        flip_bone(self.obj, ctrl_name)

        # Create tweak
        tweak_bone   = copy_bone(self.obj, hip_org_name, ctrl_name )
        tweak_bone_e = eb[tweak_bone]
        tweak_bone_e.length /= 2

        hips_dict = {
            'ctrl'    : ctrl_bone, 
            'tweak'   : tweak_bone, 
        }
        
        return hips_dict
        
        
    def create_back( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        back_org_bones = [ 'ORG-spine', 'ORG-ribs', 'ORG-ribs.001' ]
        
        # Create ribs ctrl bone
        ribs_ctrl_name = strip_org( back_org_bones[1] )
        ribs_ctrl_name = copy_bone( 
            self.obj, 
            back_org_bones[2], 
            ribs_ctrl_name
        )

        ribs_ctrl_bone_e        = eb[ ribs_ctrl_name ]
        ribs_ctrl_bone_e.parent = None

        # Position the head of the ribs control bone a bit lower to 
        # change the rotation pivot
        org_ribs_2_e = eb[ back_org_bones[1] ]
        ribs_ctrl_bone_e.head[:] = \
            org_ribs_2_e.tail - ( org_ribs_2_e.tail - org_ribs_2_e.head ) / 3
        
        # Create mch_drv bone
        mch_drv_bones = []        
        for i in range(2):
            mch_drv_name = make_mechanism_name( 
                strip_org( back_org_bones[i] ) 
            ) + '_DRV'

            mch_drv_name = copy_bone(
                self.obj,
                back_org_bones[i],
                mch_drv_name 
            )
            
            mch_drv_bone_e         = eb[ mch_drv_name ]
            mch_drv_bone_e.parent  = None
            mch_drv_bone_e.length /= 4

            mch_drv_bones.append( mch_drv_name )
        
        tweak_bones = []

        for org in back_org_bones:
            # Create tweak bones
            tweak_name = strip_org(org)
            tweak_name = copy_bone(self.obj, org, tweak_name )

            tweak_bone_e        = eb[ tweak_name ]
            tweak_bone_e.parent = None
            tweak_bone_e.length /= 2
            
            tweak_bones.append( tweak_name )
        
        back_dict = {
            'ribs_ctrl'     : ribs_ctrl_name,
            'mch_drv_bones' : mch_drv_bones,
            'tweak_bones'   : tweak_bones,
        }
        
        return back_dict


    def create_neck( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        neck_org_bones = sorted( 
            [ bone for bone in org_bones if 'neck' in bone.lower() ], 
            key=str.lower 
        )
        
        # Create ctrl bone
        ctrl_name = strip_org( neck_org_bones[0] )
        ctrl_name = copy_bone( self.obj,neck_org_bones[0] ,ctrl_name )
 
        ctrl_bone_e         = eb[ctrl_name]
        ctrl_bone_e.tail[:] = eb[neck_org_bones[-1]].tail

        # Create mch rotation bone
        mch_rotation_name = make_mechanism_name( ctrl_name ) + '_rotation'
        mch_rotation_name = copy_bone(
            self.obj, 
            'ribs', 
            mch_rotation_name 
        )

        mch_rot_e = eb[ mch_rotation_name ]
        
        # Position and scale mch rotation bone
        put_bone( self.obj, mch_rotation_name, eb[ neck_org_bones[0] ].head )
        mch_rot_e.length /= 3

        # Create mch drv bone
        mch_drv_name   = make_mechanism_name( ctrl_name ) + '_DRV'
        mch_drv_name   = copy_bone( self.obj, neck_org_bones[1], mch_drv_name )
        mch_drv_e      = eb[ mch_drv_name ]
        mch_drv_e.length /= 4
        
        tweak_bones   = []
        for org in neck_org_bones:
            # Create tweak bones
            tweak_name   = copy_bone( self.obj, org, ctrl_name )
            tweak_bone_e = eb[ tweak_name ]
            tweak_bone_e.length /= 2
            
            tweak_bones.append( tweak_name )
            
        neck_dict = {
            'ctrl'        : ctrl_name,
            'mch_rot'     : mch_rotation_name,
            'mch_drv'     : mch_drv_name,
            'tweak_bones' : tweak_bones,
        }
        
        return neck_dict    


    def create_head( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create ctrl bone
        ctrl_name = strip_org( org_bones[-1] )
        ctrl_name = copy_bone( self.obj, org_bones[-1], ctrl_name )
        
        # Create mch rotation bone
        mch_rotation_name = make_mechanism_name( ctrl_name ) + '_rotation'
        mch_rotation_name = copy_bone( 
            self.obj, 
            'neck', 
            mch_rotation_name 
        )

        # Position and scale mch rotation bone
        mch_rot_e = eb[ mch_rotation_name ]
        put_bone( self.obj, mch_rotation_name, eb[ org_bones[-1] ].head )
        mch_rot_e.length /= 3
        
        # Create mch drv bone
        mch_drv_name = make_mechanism_name( ctrl_name ) + '_DRV'
        mch_drv_name = copy_bone( self.obj, org_bones[-1], mch_drv_name )

        # Scale mch drv bone to a fourth of its size
        mch_drv_e      = eb[mch_drv_name]
        mch_drv_e.length /= 4
        
        head_dict = {
            'ctrl'    : ctrl_name, 
            'mch_rot' : mch_rotation_name, 
            'mch_drv' : mch_drv_name 
        }
        
        return head_dict


    def create_deformation( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        def_bones = []
        for org in org_bones:
            def_name = make_deformer_name( strip_org( org ) )
            def_name = copy_bone( self.obj, org, def_name )
            def_bones.append( def_name )
        
        return { 'def_bones' : def_bones }


    def create_bones(self):
        org_bones = self.org_bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None
        
        torso       = self.create_torso()
        hips        = self.create_hips()
        back        = self.create_back()
        neck        = self.create_neck()
        head        = self.create_head()
        deformation = self.create_deformation()
        
        all_bones = {
            'torso' : torso,
            'hips'  : hips,
            'back'  : back,
            'neck'  : neck,
            'head'  : head,
            'def'   : deformation
        }
        
        return all_bones


    def parent_bones(self, all_bones):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Clearing out previous parenting save the org bones
        for category in all_bones:
            for bones in all_bones[category]:
                if isinstance( all_bones[category][bones], list ):
                    for bone in all_bones[category][bones]:
                        eb[bone].parent = None
                else:
                    eb[ all_bones[category][bones] ].parent = None
        
        # Parenting the torso bone
        torso_name = all_bones['torso']['ctrl']
        torso_ctrl_e = eb[ torso_name ]
        torso_ctrl_e.parent = None  # Later rigify will parent to root
        
        # Parenting the hips' bones
        hips_ctrl          = all_bones['hips']['ctrl']        
        hips_ctrl_e        = eb[ hips_ctrl ]        
        hips_ctrl_e.parent = torso_ctrl_e

        hips_tweak_name     = all_bones['hips']['tweak']
        hips_tweak_e        = eb[hips_tweak_name]
        hips_tweak_e.parent = hips_ctrl_e
        
        # Parenting the back bones
        ribs_ctrl_name     = all_bones['back']['ribs_ctrl']        
        ribs_ctrl_e        = eb[ribs_ctrl_name]
        ribs_ctrl_e.parent = torso_ctrl_e

        back_mch_drv_names   = all_bones['back']['mch_drv_bones']
        back_mch_drvs_e = [ eb[bone] for bone in back_mch_drv_names ]

        back_mch_drvs_e[0].parent = hips_ctrl_e
        back_mch_drvs_e[1].parent = torso_ctrl_e

        back_tweak_names = all_bones['back']['tweak_bones']
        back_tweaks_e    = [ eb[bone] for bone in back_tweak_names ]
        
        back_tweaks_e[0].parent = back_mch_drvs_e[0]
        back_tweaks_e[1].parent = back_mch_drvs_e[1]
        back_tweaks_e[2].parent = ribs_ctrl_e
        
        # Parenting the neck bones
        neck_mch_rot     = all_bones['neck']['mch_rot']
        neck_ctrl_name   = all_bones['neck']['ctrl']
        neck_mch_drv     = all_bones['neck']['mch_drv']
        neck_tweak_names = all_bones['neck']['tweak_bones']
        
        neck_mch_rot_e  = eb[ neck_mch_rot ]
        neck_ctrl_e     = eb[neck_ctrl_name]
        neck_mch_drv_e  = eb[ neck_mch_drv ]
        neck_tweaks_e   = [ eb[bone] for bone in neck_tweak_names ]
        
        neck_mch_rot_e.parent   = None  # Later rigify will parent to root
        neck_ctrl_e.parent      = neck_mch_rot_e
        neck_mch_drv_e.parent   = neck_ctrl_e
        neck_tweaks_e[0].parent = neck_ctrl_e
        neck_tweaks_e[1].parent = neck_mch_drv_e
        
        # Parenting the head bones
        head_mch_rot = all_bones['head']['mch_rot']
        head_ctrl    = all_bones['head']['ctrl']
        head_mch_drv = all_bones['head']['mch_drv']
        
        head_mch_rot_e = eb[ head_mch_rot ]
        head_ctrl_e    = eb[ head_ctrl    ]
        head_mch_drv_e = eb[ head_mch_drv ]
        
        head_mch_rot_e.parent = None  # Later rigify will parent to root
        head_ctrl_e.parent    = head_mch_rot_e
        head_mch_drv_e.parent = neck_ctrl_e
        
        # Parenting the deformation bones
        def_names   = all_bones['def']['def_bones']
        def_bones_e = [ eb[bone] for bone in def_names ]

        for bone in def_bones_e:
            if def_bones_e.index(bone) == 0:
                bone.parent = None # Later rigify will parent to root
            # While the rest use simple chain parenting
            else:
                bone.parent = def_bones_e[ def_bones_e.index(bone) - 1 ]
                if def_bones_e.index(bone) != len(def_bones_e) - 1:
                    bone.use_connect = True
        
        ## Parenting the org bones to tweak
        parent_bones = \
            [hips_tweak_name] + back_tweak_names + neck_tweak_names + [head_ctrl]
        
        for bone, parent in zip( org_bones, parent_bones ):
            eb[bone].use_connect = False
            eb[bone].parent      = eb[parent]
            

    def constraints_data( self, all_bones ):
        ## Big mama: the dict that contains all the info about the constraints
        
        constraint_data = {}
        
        org_bones = self.org_bones
        
        # Deformation bone names (1)
        def_bones = all_bones['def']['def_bones']

        # Referencing def subtargets: tweak bones + head control
        hips_tweak  = all_bones['hips']['tweak']
        back_tweaks = all_bones['back']['tweak_bones']
        neck_tweaks = all_bones['neck']['tweak_bones']
        head_ctrl   = all_bones['head']['ctrl']

        def_bones_subtargets = \
            [hips_tweak] + back_tweaks + neck_tweaks + [head_ctrl]

        for bone, subtarget in zip( def_bones, def_bones_subtargets ):
            if def_bones.index( bone ) != def_bones.index( def_bones[-1] ):
                next_index     = def_bones.index( bone ) + 1
                next_subtarget = def_bones_subtargets[ next_index ]
                
                constraint_data[ bone ] = [ 
                    { 'constraint': 'COPY_TRANSFORMS',
                      'subtarget' : subtarget        },
                    { 'constraint': 'DAMPED_TRACK', 
                      'subtarget' : next_subtarget   },
                    { 'constraint': 'STRETCH_TO',
                      'subtarget' : next_subtarget   } 
                ]

            else:
                constraint_data[ bone ] = [ 
                    { 'constraint': 'COPY_TRANSFORMS',
                      'subtarget' : subtarget        }
                ]
        
        # MCH Rotation bone names (2)
        neck_mch_rot = all_bones['neck']['mch_rot']
        head_mch_rot = all_bones['head']['mch_rot']

        # MCH rot subtargets:
        ribs_ctrl = all_bones['back']['ribs_ctrl']
        neck_ctrl = all_bones['neck']['ctrl']

        for bone, subtarget in zip( 
            [ neck_mch_rot, head_mch_rot ], [ ribs_ctrl, neck_ctrl ] ):
        
            constraint_data[ bone ] = [ 
                { 'constraint': 'COPY_LOCATION',
                  'subtarget' : subtarget,
                  'head_tail' : 1.0              },
                { 'constraint': 'COPY_ROTATION', 
                  'subtarget' : subtarget        }
            ]

        # MCH DRV bone names (3)
        back_mch_drvs = all_bones['back']['mch_drv_bones']
        
        constraint_data[ back_mch_drvs[0] ] = [ 
            { 'constraint': 'DAMPED_TRACK',
              'subtarget' : back_tweaks[1]  }       
        ]

        constraint_data[ back_mch_drvs[1] ] = [ 
            { 'constraint'  : 'COPY_TRANSFORMS',
              'subtarget'   : ribs_ctrl,
              'influence'   : 0.5,
              'ownerspace'  : 'LOCAL',
              'targetspace' : 'LOCAL'            },
            { 'constraint'  : 'DAMPED_TRACK', 
              'subtarget'   : back_tweaks[2]     }
        ]

        neck_mch_drv  = all_bones['neck']['mch_drv']

        constraint_data[ neck_mch_drv ] = [ 
            { 'constraint'  : 'COPY_TRANSFORMS',
              'subtarget'   : head_ctrl,
              'influence'   : 0.5,
              'ownerspace'  : 'LOCAL',
              'targetspace' : 'LOCAL'                       }
        ]

        head_mch_drv  = all_bones['head']['mch_drv']

        constraint_data[ head_mch_drv ] = [
            { 'constraint': 'COPY_LOCATION',
              'subtarget' : head_ctrl,       }
        ]
        
        return constraint_data


    def set_constraints( self, constraint_data ):
        for bone in constraint_data:
            for constraint in constraint_data[bone]:
                self.make_constraint(bone, constraint)


    def make_constraint( self, bone, constraint ):
        const_type = constraint['constraint']
        subtarget  = constraint['subtarget']
        
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        owner_pb = pb[bone]
        const = owner_pb.constraints.new( const_type )
        
        const.target    = self.obj
        const.subtarget = subtarget
        
        try:
            const.influence = constraint['influence']
        except:
            pass
        
        try:
            const.head_tail = constraint['head_tail']
        except:
            pass

        try:
            const.owner_space = constraint['ownerspace']
        except:
            pass

        try:
            const.target_space = constraint['targetspace']
        except:
            pass

    def drivers_and_props( self, all_bones ):
        
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        # Referencing all relevant bones
        torso_name = all_bones['torso']['ctrl']
        pb_torso = pb[torso_name]
        
        neck_mch_rot = all_bones['neck']['mch_rot']
        head_mch_rot = all_bones['head']['mch_rot']
        
        owner_mch_rot_bones = [ neck_mch_rot, head_mch_rot ]
        
        # Setting the torso's props
        props_list = [ "neck_follow", "head_follow" ]
        
        for prop in props_list:
            
            if prop == 'neck_follow':
                pb_torso[prop] = 0.5
            else:
                pb_torso[prop] = 0.0

            prop = rna_idprop_ui_prop_get( pb_torso, prop )
            prop["min"] = 0.0
            prop["max"] = 1.0
            prop["soft_min"] = 0.0
            prop["soft_max"] = 1.0
            prop["description"] = prop
        
        # driving the follow rotation switches for neck and head
        for bone, prop, in zip( owner_mch_rot_bones, props_list ):
            drv = pb[ bone ].constraints[ 1 ].driver_add("influence").driver
            drv.type='SUM'
            
            var = drv.variables.new()
            var.name = prop
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = \
                pb_torso.path_from_id() + '['+ '"' + prop + '"' + ']'
        

    def bone_properties( self, all_bones ):
        ## Setting all the properties of the bones relevant to posemode
        
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        # Referencing relevant bones
        hips_tweak_name  = all_bones['hips']['tweak']
        back_tweak_names = all_bones['back']['tweak_bones']
        neck_tweak_names = all_bones['neck']['tweak_bones']
        
        tweak_names = [ hips_tweak_name ] + back_tweak_names + neck_tweak_names
        
        def_names = all_bones['def']['def_bones']
        
        # deformation bones bbone segements
        
        for bone in def_names[1:-1]:
            
            self.obj.data.bones[bone].bbone_segments = 8
        
        # control locks - tweak bones
        for bone in tweak_names:
            pb[bone].lock_rotation = True, False, True
            pb[bone].lock_scale    = False, True, False


    def assign_widgets( self, all_bones ):
        
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        # Referencing the all animatable bones
        
        torso_name      = all_bones['torso']['ctrl']
        
        hips_ctrl_name  = all_bones['hips']['ctrl']
        ribs_ctrl_name  = all_bones['back']['ribs_ctrl']
        neck_ctrl_name  = all_bones['neck']['ctrl']
        head_ctrl_name  = all_bones['head']['ctrl']
        
        control_names = [ 
            hips_ctrl_name, 
            ribs_ctrl_name, 
            neck_ctrl_name, 
            head_ctrl_name 
        ]
        
        hips_tweak_name  = all_bones['hips']['tweak']
        back_tweak_names = all_bones['back']['tweak_bones']
        neck_tweak_names = all_bones['neck']['tweak_bones']
        
        tweak_names = [ hips_tweak_name ] + back_tweak_names + neck_tweak_names
        
        # Assigning a widget to torso bone
        create_cube_widget(
            self.obj, 
            torso_name, 
            radius              = 0.5, 
            bone_transform_name = None
        )
        
        # Assigning widgets to control bones
        for bone in control_names:
            create_circle_widget(
                self.obj, 
                bone, 
                radius              = 1.25, 
                head_tail           = 0.5, 
                with_line           = False, 
                bone_transform_name = None
            )
        
        # Assigning widgets to tweak bones and layers
        for bone in tweak_names:
            create_sphere_widget(self.obj, bone, bone_transform_name=None)
            
            if self.tweak_layers:
                pb[bone].bone.layers = self.tweak_layers
        
        all_controls = [ torso_name ] + control_names + tweak_names

        return all_controls

    def generate(self):
        
        all_bones = self.create_bones()
        self.parent_bones( all_bones )
        constraint_data = self.constraints_data( all_bones )
        self.set_constraints( constraint_data )
        self.drivers_and_props( all_bones )
        self.bone_properties( all_bones )
        all_controls = self.assign_widgets( all_bones )

        torso_name      = all_bones['torso']['ctrl']
        neck_ctrl_name  = all_bones['neck']['ctrl']
        head_ctrl_name  = all_bones['head']['ctrl']

        # Create UI
        controls_string = ", ".join(["'" + x + "'" for x in all_controls])
        return [script % (
            controls_string, 
            head_ctrl_name, 
            neck_ctrl_name, 
            self.obj.name, 
            torso_name, 
            'head_follow',
            'neck_follow'
            )]

def add_parameters( params ):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """
    # varifying the name of the torso bone
    params.torso_name = bpy.props.StringProperty(
        name="torso_name", 
        default="torso",
        description="The name of the torso master control bone"
        )

    # Setting up extra layers for the FK and tweak
    params.tweak_extra_layers = bpy.props.BoolProperty( 
        name        = "tweak_extra_layers", 
        default     = True, 
        description = ""
        )

    params.tweak_layers = bpy.props.BoolVectorProperty(
        size        = 32,
        description = "Layers for the tweak controls to be on",
        default     = tuple( [ i == 1 for i in range(0, 32) ] )
        )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""
    
    r = layout.row()
    r.prop(params, "torso_name")
        
    r = layout.row()
    r.prop(params, "tweak_extra_layers")
    r.active = params.tweak_extra_layers
    
    col = r.column(align=True)
    row = col.row(align=True)
    row.prop(params, "tweak_layers", index=0, toggle=True, text="")
    row.prop(params, "tweak_layers", index=1, toggle=True, text="")
    row.prop(params, "tweak_layers", index=2, toggle=True, text="")
    row.prop(params, "tweak_layers", index=3, toggle=True, text="")
    row.prop(params, "tweak_layers", index=4, toggle=True, text="")
    row.prop(params, "tweak_layers", index=5, toggle=True, text="")
    row.prop(params, "tweak_layers", index=6, toggle=True, text="")
    row.prop(params, "tweak_layers", index=7, toggle=True, text="")
    row = col.row(align=True)
    row.prop(params, "tweak_layers", index=16, toggle=True, text="")
    row.prop(params, "tweak_layers", index=17, toggle=True, text="")
    row.prop(params, "tweak_layers", index=18, toggle=True, text="")
    row.prop(params, "tweak_layers", index=19, toggle=True, text="")
    row.prop(params, "tweak_layers", index=20, toggle=True, text="")
    row.prop(params, "tweak_layers", index=21, toggle=True, text="")
    row.prop(params, "tweak_layers", index=22, toggle=True, text="")
    row.prop(params, "tweak_layers", index=23, toggle=True, text="")
    
    col = r.column(align=True)
    row = col.row(align=True)
    row.prop(params, "tweak_layers", index=8, toggle=True, text="")
    row.prop(params, "tweak_layers", index=9, toggle=True, text="")
    row.prop(params, "tweak_layers", index=10, toggle=True, text="")
    row.prop(params, "tweak_layers", index=11, toggle=True, text="")
    row.prop(params, "tweak_layers", index=12, toggle=True, text="")
    row.prop(params, "tweak_layers", index=13, toggle=True, text="")
    row.prop(params, "tweak_layers", index=14, toggle=True, text="")
    row.prop(params, "tweak_layers", index=15, toggle=True, text="")
    row = col.row(align=True)
    row.prop(params, "tweak_layers", index=24, toggle=True, text="")
    row.prop(params, "tweak_layers", index=25, toggle=True, text="")
    row.prop(params, "tweak_layers", index=26, toggle=True, text="")
    row.prop(params, "tweak_layers", index=27, toggle=True, text="")
    row.prop(params, "tweak_layers", index=28, toggle=True, text="")
    row.prop(params, "tweak_layers", index=29, toggle=True, text="")
    row.prop(params, "tweak_layers", index=30, toggle=True, text="")
    row.prop(params, "tweak_layers", index=31, toggle=True, text="")


def create_sample(obj):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('hips')
    bone.head[:] = 0.0000, 0.0351, 1.0742
    bone.tail[:] = -0.0000, 0.0059, 1.1910
    bone.roll = 0.0000
    bone.use_connect = False
    bones['hips'] = bone.name
    bone = arm.edit_bones.new('spine')
    bone.head[:] = -0.0000, 0.0059, 1.1910
    bone.tail[:] = 0.0000, 0.0065, 1.2768
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['hips']]
    bones['spine'] = bone.name
    bone = arm.edit_bones.new('ribs')
    bone.head[:] = 0.0000, 0.0065, 1.2768
    bone.tail[:] = -0.0000, 0.0251, 1.3655
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['spine']]
    bones['ribs'] = bone.name
    bone = arm.edit_bones.new('ribs.001')
    bone.head[:] = -0.0000, 0.0251, 1.3655
    bone.tail[:] = 0.0000, 0.0217, 1.4483
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ribs']]
    bones['ribs.001'] = bone.name
    bone = arm.edit_bones.new('neck')
    bone.head[:] = 0.0000, 0.0217, 1.4483
    bone.tail[:] = 0.0000, 0.0092, 1.4975
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ribs.001']]
    bones['neck'] = bone.name
    bone = arm.edit_bones.new('neck.001')
    bone.head[:] = 0.0000, 0.0092, 1.4975
    bone.tail[:] = -0.0000, -0.0013, 1.5437
    bone.roll = -0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['neck']]
    bones['neck.001'] = bone.name
    bone = arm.edit_bones.new('head')
    bone.head[:] = -0.0000, -0.0013, 1.5437
    bone.tail[:] = -0.0000, -0.0013, 1.7037
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['neck.001']]
    bones['head'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['hips']]
    pbone.rigify_type = 'pitchipoy.turbo_torso'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.extra_layers = [False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_layers = [False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.fk_layers = [False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['spine']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ribs']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ribs.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['neck']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['neck.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['head']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        arm.edit_bones.active = bone

if __name__ == "__main__":
    create_sample(bpy.context.active_object) 
