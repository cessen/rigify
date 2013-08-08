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
        """ Initialize torso rig and key rig properties """

        self.obj       = obj
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)
        self.params    = params

        # Check if user provided the positions of the neck and pivot
        if params.neck_pos and params.pivot_pos:
            self.neck_pos  = params.neck_pos
            self.pivot_pos = params.pivot_pos
        else:
            raise MetarigError(
                "RIGIFY ERROR: please specify neck and pivot bone positions"
            )

        # Check if neck is lower than pivot
        if params.neck_pos >= params.pivot_pos:
            raise MetarigError(
                "RIGIFY ERROR: Neck cannot be below or the same as pivot"
            )

        # TODO:
        # Limit neck_pos prop  to 1 --> num of bones - 1 (last is head)
        # Limit pivot_pos prop to 2 --> num of bones (must leave place for lower torso)

        if params.tail_pos:
            self.tail_pos = params.tail_pos

        # Assign values to tweak layers props if opted by user
        if params.tweak_extra_layers:
            self.tweak_layers = list(params.tweak_layers)
        else:
            self.tweak_layers = None

        # Report error of user created less than the minimum of 4 bones for rig
        if len(self.org_bones) <= 4:
            raise MetarigError(
                "RIGIFY ERROR: invalid rig structure" % (strip_org(bone_name))
            )            


    def build_bone_structure( self ):
        """ Divide meta-rig into lists of bones according to torso rig anatomy:
            Neck --> Upper torso --> Lower torso --> Tail (optional) """

        if self.pivot_pos and self.neck_pos:
    
            neck_index  = self.neck_pos  - 1
            pivot_index = self.pivot_pos - 1
            tail_index  = self.tail_pos  - 1
     
            neck_bones        = self.org_bones[neck_index::]
            upper_torso_bones = self.org_bones[pivot_index:neck_index]
            lower_torso_bones = self.org_bones[tail_index:pivot_index+1]

            tail_bones        = []
            if tail_index:
                tail_bones    = self.org_bones[::tail_index+1]

            return {
                'neck'  : neck_bones,
                'upper' : upper_torso_bones, 
                'lower' : lower_torso_bones, 
                'tail'  : tail_bones
            }

        else:
            return 'ERROR'

    def orient_bone( self, eb, axis, scale, reverse = False ):
        v = Vector((0,0,0))
       
        setattr(v,axis,scale)

        if reverse:
            tail_vec = v * self.obj.matrix_world
            eb.head[:] = eb.tail
            eb.tail[:] = eb.head + tail_vec     
        else:
            tail_vec = v * self.obj.matrix_world
            eb.tail[:] = eb.head + tail_vec


    def create_pivot( self, pivot ):
        """ Create the pivot control and mechanism bones """
        pivot_name = self.org_bones[pivot]

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create torso control bone    
        torso_name = 'torso'
        ctrl_name  = copy_bone(self.obj, pivot_name, torso_name)
        ctrl_eb    = eb[ ctrl_name ]
        
        self.orient_bone( ctrl_eb, 'y', 0.25 )
        
        # Create mch_pivot
        mch_name = make_mechanism_name( strip_org( pivot_name ) )
        mch_name = copy_bone(self.obj, ctrl_name, mch_name)
        mch_eb   = eb[ mch_name ]
        
        mch_eb.length /= 4

        return {
            'ctrl' : ctrl_name,
            'mch'  : mch_name
        }

        
    def create_deformation( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        def_bones = []
        for org in org_bones:
            def_name = make_deformer_name( strip_org( org ) )
            def_name = copy_bone( self.obj, org, def_name )
            def_bones.append( def_name )
        
        return def_bones

        
    def create_neck( self, neck_bones ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create neck control
        neck    = copy_bone( self.obj, org(neck_bones[0], 'neck' )
        neck_eb = eb[ neck ]

        # Neck spans all neck bones (except head)
        neck_eb.tail[:] = eb[ org(neck_bones[-1]) ].head

        # Create head control
        head = copy_bone( self.obj, org(neck_bones[-1]), 'head' )

        # MCH bones
        # Neck MCH rotation
        mch_neck = copy_bone( 
            self.obj, neck, make_mechanism_name('ROT-neck')
        )

        self.orient_bone( eb[mch_neck], 'y', 0.01 )

        # Head MCH rotation
        mch_head = copy_bone( 
            self.obj, head, make_mechanism_name('ROT-head')
        )

        self.orient_bone( eb[mch_head], 'y', 0.01 )

        twk,mch = [],[]

        # Intermediary bones
        for b in neck_bones[1:-1]: # All except 1st neck and (last) head
            mch_name = copy_bone( self.obj, org(b), make_mechanism_name(b) )
            eb[mch_name].length /= 4

            mch += [ mch_name ]

        # Tweak bones
        for b in neck_bones[:-1]: # All except last bone
            twk_name = "tweak_" + b
            twk_name = copy_bone( self.obj, org(b), twk_name )            
            
            eb[twk_name].length /= 2

            twk += [ twk_name ]

        return {
            'ctrl_neck' : neck,
            'ctrl'      : head,
            'mch_neck'  : mch_neck,
            'mch_head'  : mch_head,
            'mch'       : mch,
            'tweak'     : twk
        }


    def create_chest( self, chest_bones ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create chest control bone
        chest = copy_bone( self.obj, org( chest_bones[0] ), 'chest' )
        self.orient_bone( eb[chest], 'y', 0.2 )
        
        # Create mch and twk bones
        twk,mch = [],[]
        
        for b in chest_bones:
            mch_name = copy_bone( self.obj, org(b), make_mechanism_name(b) )
            orient_bone( eb[mch_name], 'y', 0.01 )

            twk_name = "tweak_" + b
            twk_name = copy_bone( self.obj, org(b), twk_name )
            eb[twk_name].length /= 2

            mch += [ mch_name ]
            twk += [ twk_name ]

        return {
            'ctrl'  : chest,
            'mch'   : mch,
            'tweak' : twk
        }


    def create_hips( self, hip_bones ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create hips control bone
        hips = copy_bone( self.obj, org( hip_bones[-1] ), 'hips' )
        orient_bone( eb[hips], 'y', 0.1, reverse = True )

        # Create mch and tweak bones
        twk,mch = [],[]
        for b in hip_bones:
            mch_name = copy_bone( self.obj, org(b), make_mechanism_name(b) )
            orient_bone( eb[mch_name], 'y', 0.01, reverse = True )

            twk_name = "tweak_" + b
            twk_name = copy_bone( self.obj, org( b ), twk_name )
            
            eb[twk_name].length /= 2

            mch += [ mch_name ]
            twk += [ twk_name ]

        return {
            'ctrl'  : hips,
            'mch'   : mch,
            'tweak' : twk
        }


    def parent_bones( self, bones ):
        
        org bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Parent deform bones
        for i,b in enumerate( bones['def_bones'] ):
            if i > 0: # For all bones but the first (which has no parent)
                eb[b].parent      = eb[ bones['def_bones'][i-1] ] # to previous
                eb[b].use_connect = True
        
        # Parent control bones
        # Head control => MCH-rotation_head
        eb[ bones['neck']['ctrl'] ].parent = eb[ bones['neck']['mch_head'] ]

        # Neck control => MCH-rotation_neck
        eb[ bones['neck']['ctrl_neck'] ].parent = eb[ bones['neck']['mch_neck'] ]

        # Parent hips and chest controls to torso
        eb[ bones['chest']['ctrl'] ].parent = eb[ bones['pivot']['ctrl'] ]
        eb[ bones['hips']['ctrl'] ].parent  = eb[ bones['pivot']['ctrl'] ]

        # Parent mch bones
        # Neck mch
        parent = eb[ bones['neck']['ctrl_neck'] ]
        eb[ bones['neck']['mch_head'] ].parent = parent
        
        for eb in [ eb[b] for b in bones['neck']['mch'] ]:
            eb.parent = parent
            
        # Chest mch bones and neck mch
        chest_mch = bones['chest']['mch'] + bones['neck']['mch_neck']
        for i,b in enumerate(chest_mch):
            if i == 0:
                eb[b].parent = eb[ bones['pivot']['ctrl'] ]
            else:
                eb[b].parent = eb[ chest_mch[i-1] ]

        # Hips mch bones
        for i,b in enumerate( bones['hips']['mch'] ):
            if i == len(bones['hips']['mch']) - 1:
                eb[b].parent = eb[ bones['pivot']['ctrl'] ]
            else:
                eb[b].parent = eb[ bones['hips']['mch'][i+1] ]
        
        # mch pivot
        eb[ bones['pivot']['mch'].parent = eb[ bones['chest']['mch'][0] ]
        
        # Tweaks

        # Neck tweaks
        for twk,mch in zip( bones['neck']['tweak'], bones['neck']['mch'] ):
            if bones['neck']['tweak'].index( twk ) == 0:
                eb[ twk ].parent = eb[ bones['neck']['ctrl_neck'] ]
            else:
                eb[ twk ].parent = eb[ mch ]
        
        # Chest tweaks
        for twk,mch in zip( bones['chest']['tweak'], bones['chest']['mch'] ):
            if bones['chest']['tweak'].index( twk ) == 0:
                eb[ twk ].parent = eb[ bones['pivot']['mch'] ]
            else:
                eb[ twk ].parent = eb[ mch ]
                
        # Hips tweaks
        for twk,mch in zip( bones['hips']['tweak'], bones['hips']['mch'] ):
            eb[ twk ].parent = eb[ mch ]


        # Parent orgs to matching tweaks
        tweaks =  [ bones['neck']['ctrl'] ] + bones['neck']['tweak']
        tweaks += bones['chest']['tweak']   + bones['hips']['tweak']
        
        if 'tail' in bones.keys():
            tweaks += bones['tail']['tweak']

        for org, twk in zip( org_bones, tweaks ):
            eb[ org ].parent = eb[ twk ]


    def make_constraint( self, bone, constraint ):
        bpy.ops.object.mode_set(mode = 'OBJECT')
        pb = self.obj.pose.bones

        owner_pb     = pb[bone]
        const        = owner_pb.constraints.new( constraint['constraint'] )
        const.target = self.obj

        # filter contraint props to those that actually exist in the currnet 
        # type of constraint, then assign values to each
        for p in [ k for k in constraint.keys() if k in dir(const) ]:
            setattr( const, p, constraint[p] )


    def constrain_bones( self, bones ):
        # MCH bones

        # head and neck MCH bones
        for b in [ bones['neck']['head_mch'], bones['neck']['neck_mch'] ]:
            self.make_constraint( b, { 
                'constraint' : 'COPY_ROTATION',
                'subtarget'  : bones['pivot']['ctrl'],
            } )
            self.make_constraint( b, { 
                'constraint' : 'COPY_SCALE',
                'subtarget'  : bones['pivot']['ctrl'],
            } )
            
        # Intermediary mch bones
        intermediaries = [ bones['neck'], bones['chest'], bones['hips'] ]
        
        if tail in bones.keys():
            intermediaries += bones['tail']

        for l in intermediaries:
            mch    = l['mch']
            factor = float( 1 / len( l['tweak'] ) )

            for b in mch:
                self.make_constraint( b, { 
                    'constraint'  : 'COPY_TRANSFORMS',
                    'subtarget'   : l['ctrl'],
                    'infuence'    : factor,
                    'ownerspace'  : 'LOCAL',
                    'targetspace' : 'LOCAL'
                } )
        
        # MCH pivot
        self.make_constraint( bones['pivot']['mch'], {
            'constraint'  : 'COPY_TRANSFORMS',
            'subtarget'   : bones['hips']['mch'][-1],
            'ownerspace'  : 'LOCAL',
            'targetspace' : 'LOCAL'
        })
        
        # DEF bones
        deform =  bones['deform']
        tweaks =  [ bones['neck']['ctrl'] ] + bones['neck']['tweak'] 
        tweaks += bones['chest']['tweak']   + bones['hips']['tweak']

        for d,t in zip(deform, tweaks[::-1]):
            tidx = tweaks.index[t]

            self.make_constraint( bones['pivot']['mch'], {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : t
            })

            if tidx != len(tweaks) - 1:
                self.make_constraint( bones['pivot']['mch'], {
                    'constraint'  : 'DAMPED_TRACK',
                    'subtarget'   : tweaks[ tidx + 1 ],
                })

                self.make_constraint( bones['pivot']['mch'], {
                    'constraint'  : 'STRETCH_TO',
                    'subtarget'   : tweaks[ tidx + 1 ],
                })

            
    def create_drivers( self, bones ):
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        # Setting the torso's props
        torso = pb[ bones['pivot']['ctrl'] ]

        props  = [ "head_follow", "neck_follow" ]
        owners = [ bones['neck']['ctrl'], bones['neck']['neck_ctrl'] ]
        
        for prop in props:
            if prop == 'neck_follow':
                torso[prop] = 0.5
            else:
                torso[prop] = 0.0

            prop = rna_idprop_ui_prop_get( pb_torso, prop )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = prop
        
        # driving the follow rotation switches for neck and head
        for bone, prop, in zip( owners, props ):
            # Add driver to copy rotation constraint
            drv = pb[ bone ].constraints[ 0 ].driver_add("influence").driver
            drv.type = 'SUM'
            
            var = drv.variables.new()
            var.name = prop
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = \
                pb_torso.path_from_id() + '['+ '"' + prop + '"' + ']'

    
    def locks_and_widgets( self, bones ):
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones

        # deform bones bbone segements
        for bone in bones['deform'][:-1]:
            self.obj.data.bones[bone].bbone_segments = 8

        self.obj.data.bones[ bones['deform'][0]  ].bbone_in  = 0.0
        self.obj.data.bones[ bones['deform'][-2] ].bbone_out = 0.0

        # Locks
        tweaks =  bones['neck']['tweak'] + bones['chest']['tweak']
        tweaks += bones['hips']['tweak']
        
        if 'tail' in bones.keys():
            tweaks += bones['tail']['tweak']

        # Tweak bones locks
        for bone in tweaks:
            pb[bone].lock_rotation = True, False, True
            pb[bone].lock_scale    = False, True, False

        # Widgets
        hips_tweak_name  = all_bones['hips']['tweak']
        back_tweak_names = all_bones['back']['tweak_bones']
        neck_tweak_names = all_bones['neck']['tweak_bones']
        
        tweak_names = [ hips_tweak_name ] + back_tweak_names + neck_tweak_names
        
        # Assigning a widget to torso bone
        create_cube_widget(
            self.obj, 
            bones['pivot']['ctrl'], 
            radius              = 0.5, 
            bone_transform_name = None
        )
        
        # Assigning widgets to control bones
        gen_ctrls = [ 
            bones['neck']['neck_ctrl'], 
            bones['chest']['ctrl'],
            bones['hips']['ctrl']
        ]
        
        if 'tail' in bones.keys():
            gen_ctrls += [ bones['tail']['ctrl'] ]
            
        for bone in gen_ctrls:
            create_circle_widget(
                self.obj, 
                bone, 
                radius              = 1.25, 
                head_tail           = 0.5, 
                with_line           = False, 
                bone_transform_name = None
            )

        # Head widget
        create_circle_widget(
            self.obj, 
            bones['neck']['ctrl'], 
            radius              = 1.25, 
            head_tail           = 1.0, 
            with_line           = False, 
            bone_transform_name = None
        )

        # place widgets on correct bones
        chest_widget_loc = bones['deform'][self.neck_pos -2]
        pb[ bones['chest']['ctrl'] ].custom_shape_transform = chest_widget_loc

        hips_widget_loc = bones['deform'][0]
        if self.tail_pos:
            hips_widget_loc = bones['deform'][self.tail_pos -1]

        pb[ bones['hips']['ctrl'] ].custom_shape_transform = hips_widget_loc

        # Assigning widgets to tweak bones and layers
        for bone in tweak_names:
            create_sphere_widget(self.obj, bone, bone_transform_name=None)
            
            if self.tweak_layers:
                pb[bone].bone.layers = self.tweak_layers        


    def create_torso( self ):
    
        # Torso Rig Anatomy:
        # Neck: all bones above neck point, last bone is head
        # Upper torso: all bones between pivot and neck start
        # Lower torso: all bones below pivot until tail point
        # Tail: all bones below tail point

        bone_chains = self.build_bone_structure()

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in self.org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None

        if bone_chains != 'ERROR':

            # Create lists of bones and strip "ORG" from their names
            neck_bones        = [ strip_org(b) for b in bone_chains['neck' ] ]
            upper_torso_bones = [ strip_org(b) for b in bone_chains['upper'] ]
            lower_torso_bones = [ strip_org(b) for b in bone_chains['lower'] ]
            tail_bones        = [ strip_org(b) for b in bone_chains['tail' ] ]

            bones = {}

            bones['def']   = self.create_deform() # Gets org bones from self
            bones['torso'] = self.create_pivot( self.pivot_pos )
            bones['neck']  = self.create_neck( neck_bones )
            bones['chest'] = self.create_upper_torso( upper_torso_bones )
            bones['hips']  = self.create_lower_torso( lower_torso_bones )
            bones['tweak'] = self.create_tweaks() # Gets org bones from self
            # TODO: Add create tail

            if tail_bones:
                bones['tail'] = self.create_tail( tail_bones )

            self.parent_bones(      bones )
            self.constrain_bones(   bones )
            self.create_drivers(    bones )
            self.locks_and_widgets( bones )



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
