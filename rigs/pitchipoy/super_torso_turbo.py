import bpy
from mathutils import Vector
from ...utils import copy_bone, flip_bone, put_bone, org
from ...utils import strip_org, make_deformer_name, connected_children_names 
from ...utils import create_circle_widget, create_sphere_widget, create_widget
from ...utils import MetarigError, make_mechanism_name, create_cube_widget
from rna_prop_ui import rna_idprop_ui_prop_get

script = """
controls = [%s]
torso    = '%s'

if is_selected( controls ):
    layout.prop( pose_bones[ torso ], '["%s"]', slider = True )
    layout.prop( pose_bones[ torso ], '["%s"]', slider = True )
"""

class Rig:
    
    def __init__(self, obj, bone_name, params):
        """ Initialize torso rig and key rig properties """

        eb = obj.data.edit_bones

        self.obj          = obj
        self.org_bones    = [bone_name] + connected_children_names(obj, bone_name)
        self.params       = params
        self.spine_length = sum( [ eb[b].length for b in self.org_bones ] )

        # Check if user provided the positions of the neck and pivot
        if params.neck_pos and params.pivot_pos:
            self.neck_pos  = params.neck_pos
            self.pivot_pos = params.pivot_pos
        else:
            raise MetarigError(
                "RIGIFY ERROR: please specify neck and pivot bone positions"
            )

        # Check if neck is lower than pivot
        if params.neck_pos <= params.pivot_pos:
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

            tail_index = 0
            if 'tail_pos' in dir(self):
                tail_index  = self.tail_pos  - 1
     
            neck_bones        = self.org_bones[neck_index::]
            upper_torso_bones = self.org_bones[pivot_index:neck_index]
            lower_torso_bones = self.org_bones[tail_index:pivot_index]

            tail_bones        = []
            if tail_index:
                tail_bones = self.org_bones[::tail_index+1]

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
        org_bones  = self.org_bones
        pivot_name = org_bones[pivot-1]

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create torso control bone    
        torso_name = 'torso'
        ctrl_name  = copy_bone(self.obj, pivot_name, torso_name)
        ctrl_eb    = eb[ ctrl_name ]
        
        self.orient_bone( ctrl_eb, 'y', self.spine_length / 2.5 )
        
        # Create mch_pivot
        mch_name = make_mechanism_name( 'pivot' )
        mch_name = copy_bone(self.obj, ctrl_name, mch_name)
        mch_eb   = eb[ mch_name ]
        
        mch_eb.length /= 4

        # Positioning pivot in a more usable location for animators
        pivot_loc = ( eb[ org_bones[0]].head + eb[ org_bones[0]].tail ) / 2
        put_bone( self.obj, ctrl_name, pivot_loc )

        return {
            'ctrl' : ctrl_name,
            'mch'  : mch_name
        }

        
    def create_deform( self ):
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
        neck    = copy_bone( self.obj, org(neck_bones[0]), 'neck' )
        neck_eb = eb[ neck ]

        # Neck spans all neck bones (except head)
        neck_eb.tail[:] = eb[ org(neck_bones[-1]) ].head

        # Create head control
        head = copy_bone( self.obj, org(neck_bones[-1]), 'head' )

        # MCH bones
        # Neck MCH stretch
        mch_str = copy_bone( self.obj, neck, make_mechanism_name('STR-neck') )

        # Neck MCH rotation
        mch_neck = copy_bone( 
            self.obj, neck, make_mechanism_name('ROT-neck')
        )

        self.orient_bone( eb[mch_neck], 'y', self.spine_length / 10 )

        # Head MCH rotation
        mch_head = copy_bone( 
            self.obj, head, make_mechanism_name('ROT-head')
        )

        self.orient_bone( eb[mch_head], 'y', self.spine_length / 10 )

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
            'mch_str'   : mch_str,
            'mch_neck'  : mch_neck,
            'mch_head'  : mch_head,
            'mch'       : mch,
            'tweak'     : twk
        }


    def create_chest( self, chest_bones ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # get total spine length
        
        # Create chest control bone
        chest = copy_bone( self.obj, org( chest_bones[0] ), 'chest' )
        self.orient_bone( eb[chest], 'y', self.spine_length / 3 )

        # create chest mch_wgt
        mch_wgt = copy_bone( 
            self.obj, org( chest_bones[-1] ), 
            make_mechanism_name( 'WGT-chest' ) 
        )
        
        # Create mch and twk bones
        twk,mch = [],[]
        
        for b in chest_bones:
            mch_name = copy_bone( self.obj, org(b), make_mechanism_name(b) )
            self.orient_bone( eb[mch_name], 'y', self.spine_length / 10 )

            twk_name = "tweak_" + b
            twk_name = copy_bone( self.obj, org(b), twk_name )
            eb[twk_name].length /= 2

            mch += [ mch_name ]
            twk += [ twk_name ]

        return {
            'ctrl'    : chest,
            'mch'     : mch,
            'tweak'   : twk,
            'mch_wgt' : mch_wgt
        }


    def create_hips( self, hip_bones ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create hips control bone
        hips = copy_bone( self.obj, org( hip_bones[-1] ), 'hips' )
        self.orient_bone( 
            eb[hips], 
            'y', 
            self.spine_length / 4, 
            reverse = True 
        )

        # create hips mch_wgt
        mch_wgt = copy_bone( 
            self.obj, org( hip_bones[0] ), 
            make_mechanism_name( 'WGT-hips' ) 
        )

        # Create mch and tweak bones
        twk,mch = [],[]
        for b in hip_bones:
            mch_name = copy_bone( self.obj, org(b), make_mechanism_name(b) )
            self.orient_bone( 
                eb[mch_name], 'y', self.spine_length / 10, reverse = True 
            )

            twk_name = "tweak_" + b
            twk_name = copy_bone( self.obj, org( b ), twk_name )
            
            eb[twk_name].length /= 2

            mch += [ mch_name ]
            twk += [ twk_name ]

        return {
            'ctrl'    : hips,
            'mch'     : mch,
            'tweak'   : twk,
            'mch_wgt' : mch_wgt
        }


    def create_tail( self, tail_bones ):
        pass


    def parent_bones( self, bones ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
 
        # Parent deform bones
        for i,b in enumerate( bones['def'] ):
            if i > 0: # For all bones but the first (which has no parent)
                eb[b].parent      = eb[ bones['def'][i-1] ] # to previous
                eb[b].use_connect = True
        
        # Parent control bones
        # Head control => MCH-rotation_head
        eb[ bones['neck']['ctrl'] ].parent = eb[ bones['neck']['mch_head'] ]

        # MCH stretch => neck ctrl
        eb[ bones['neck']['mch_str'] ].parent = eb[ bones['neck']['ctrl_neck'] ]

        # Neck control => MCH-rotation_neck
        eb[ bones['neck']['ctrl_neck'] ].parent = eb[ bones['neck']['mch_neck'] ]

        # Parent hips and chest controls to torso
        eb[ bones['chest']['ctrl'] ].parent = eb[ bones['pivot']['ctrl'] ]
        eb[ bones['hips']['ctrl'] ].parent  = eb[ bones['pivot']['ctrl'] ]

        # Parent mch bones
        # Neck mch
        eb[ bones['neck']['mch_head'] ].parent = eb[ bones['neck']['ctrl_neck'] ]

        parent = eb[ bones['neck']['mch_str'] ]
        for i,b in enumerate([ eb[n] for n in bones['neck']['mch'] ]):
            b.parent = parent
            
        # Chest mch bones and neck mch
        chest_mch = bones['chest']['mch'] + [ bones['neck']['mch_neck'] ]
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
        eb[ bones['pivot']['mch'] ].parent = eb[ bones['chest']['mch'][0] ]

        # MCH widgets
        eb[ bones['chest']['mch_wgt'] ].parent = eb[ bones['chest']['mch'][-1] ]
        eb[ bones['hips' ]['mch_wgt'] ].parent = eb[ bones['hips' ]['mch'][0 ] ]
        
        # Tweaks

        # Neck tweaks
        for i,twk in enumerate( bones['neck']['tweak'] ):
            if i == 0:
                eb[ twk ].parent = eb[ bones['neck']['ctrl_neck'] ]
            else:
                eb[ twk ].parent = eb[ bones['neck']['mch'][i-1] ]
        
        # Chest tweaks
        for twk,mch in zip( bones['chest']['tweak'], bones['chest']['mch'] ):
            if bones['chest']['tweak'].index( twk ) == 0:
                eb[ twk ].parent = eb[ bones['pivot']['mch'] ]
            else:
                eb[ twk ].parent = eb[ mch ]
                
        # Hips tweaks
        for i,twk in enumerate(bones['hips']['tweak']):
            if i == 0:
                eb[twk].parent = eb[ bones['hips']['mch'][i] ]
            else:
                eb[twk].parent = eb[ bones['hips']['mch'][i-1] ]

        # Parent orgs to matching tweaks
        tweaks =  bones['hips']['tweak'] + bones['chest']['tweak']
        tweaks += bones['neck']['tweak'] + [ bones['neck']['ctrl'] ]

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
        for b in [ bones['neck']['mch_head'], bones['neck']['mch_neck'] ]:
            self.make_constraint( b, { 
                'constraint' : 'COPY_ROTATION',
                'subtarget'  : bones['pivot']['ctrl'],
            } )
            self.make_constraint( b, { 
                'constraint' : 'COPY_SCALE',
                'subtarget'  : bones['pivot']['ctrl'],
            } )

        # Neck MCH Stretch
        self.make_constraint( bones['neck']['mch_str'], {
            'constraint'  : 'DAMPED_TRACK',
            'subtarget'   : bones['neck']['ctrl'],
        })

        self.make_constraint( bones['neck']['mch_str'], {
            'constraint'  : 'STRETCH_TO',
            'subtarget'   : bones['neck']['ctrl'],
        })            
            
        # Intermediary mch bones
        intermediaries = [ bones['neck'], bones['chest'], bones['hips'] ]
        
        if 'tail' in bones.keys():
            intermediaries += bones['tail']

        for i,l in enumerate(intermediaries):
            mch     = l['mch']
            factor  = float( 1 / len( l['tweak'] ) )

            for j,b in enumerate(mch):
                if i == 0:
                    nfactor = float( (j + 1) / len( mch ) )
                    self.make_constraint( b, { 
                        'constraint'   : 'COPY_ROTATION',
                        'subtarget'    : l['ctrl'],
                        'influence'    : nfactor
                    } )
                else:
                    self.make_constraint( b, { 
                        'constraint'   : 'COPY_TRANSFORMS',
                        'subtarget'    : l['ctrl'],
                        'influence'    : factor,
                        'owner_space'  : 'LOCAL',
                        'target_space' : 'LOCAL'
                    } )                    

        
        # MCH pivot
        self.make_constraint( bones['pivot']['mch'], {
            'constraint'   : 'COPY_TRANSFORMS',
            'subtarget'    : bones['hips']['mch'][-1],
            'owner_space'  : 'LOCAL',
            'target_space' : 'LOCAL'
        })
        
        # DEF bones
        deform =  bones['def']
        tweaks =  bones['hips']['tweak'] + bones['chest']['tweak']
        tweaks += bones['neck']['tweak'] + [ bones['neck']['ctrl'] ]

        for d,t in zip(deform, tweaks):
            tidx = tweaks.index(t)

            self.make_constraint( d, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : t
            })

            if tidx != len(tweaks) - 1:
                self.make_constraint( d, {
                    'constraint'  : 'DAMPED_TRACK',
                    'subtarget'   : tweaks[ tidx + 1 ],
                })

                self.make_constraint( d, {
                    'constraint'  : 'STRETCH_TO',
                    'subtarget'   : tweaks[ tidx + 1 ],
                })

            
    def create_drivers( self, bones ):
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        # Setting the torso's props
        torso = pb[ bones['pivot']['ctrl'] ]

        props  = [ "head_follow", "neck_follow" ]
        owners = [ bones['neck']['mch_head'], bones['neck']['mch_neck'] ]
        
        for prop in props:
            if prop == 'neck_follow':
                torso[prop] = 0.5
            else:
                torso[prop] = 0.0

            prop = rna_idprop_ui_prop_get( torso, prop, create=True )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = prop
        
        # driving the follow rotation switches for neck and head
        for bone, prop, in zip( owners, props ):
            # Add driver to copy rotation constraint
            drv = pb[ bone ].constraints[ 0 ].driver_add("influence").driver
            drv.type = 'AVERAGE'
            
            var = drv.variables.new()
            var.name = prop
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = \
                torso.path_from_id() + '['+ '"' + prop + '"' + ']'

            drv_modifier = self.obj.animation_data.drivers[-1].modifiers[0]
            
            drv_modifier.mode            = 'POLYNOMIAL'
            drv_modifier.poly_order      = 1
            drv_modifier.coefficients[0] = 1.0
            drv_modifier.coefficients[1] = -1.0

    
    def locks_and_widgets( self, bones ):
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones

        # deform bones bbone segements
        for bone in bones['def'][:-1]:
            self.obj.data.bones[bone].bbone_segments = 8

        self.obj.data.bones[ bones['def'][0]  ].bbone_in  = 0.0
        self.obj.data.bones[ bones['def'][-2] ].bbone_out = 0.0

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

        # Assigning a widget to torso bone
        create_cube_widget(
            self.obj, 
            bones['pivot']['ctrl'], 
            radius              = 0.5, 
            bone_transform_name = None
        )
        
        # Assigning widgets to control bones
        gen_ctrls = [ 
            bones['neck']['ctrl_neck'], 
            bones['chest']['ctrl'],
            bones['hips']['ctrl']
        ]
        
        if 'tail' in bones.keys():
            gen_ctrls += [ bones['tail']['ctrl'] ]
            
        for bone in gen_ctrls:
            create_circle_widget(
                self.obj, 
                bone,
                radius              = 1.0, 
                head_tail           = 0.5, 
                with_line           = False, 
                bone_transform_name = None
            )

        # Head widget
        create_circle_widget(
            self.obj, 
            bones['neck']['ctrl'], 
            radius              = 0.75, 
            head_tail           = 1.0, 
            with_line           = False, 
            bone_transform_name = None
        )

        # place widgets on correct bones
        chest_widget_loc = pb[ bones['chest']['mch_wgt'] ]
        pb[ bones['chest']['ctrl'] ].custom_shape_transform = chest_widget_loc

        hips_widget_loc = pb[ bones['hips']['mch_wgt'] ] 
        if 'tail' in bones.keys():
            hips_widget_loc = bones['def'][self.tail_pos -1]

        pb[ bones['hips']['ctrl'] ].custom_shape_transform = hips_widget_loc

        # Assigning widgets to tweak bones and layers
        for bone in tweaks:
            create_sphere_widget(self.obj, bone, bone_transform_name=None)
            
            if self.tweak_layers:
                pb[bone].bone.layers = self.tweak_layers        


    def generate( self ):
    
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
            bones['pivot'] = self.create_pivot( self.pivot_pos )
            bones['neck']  = self.create_neck( neck_bones )
            bones['chest'] = self.create_chest( upper_torso_bones )
            bones['hips']  = self.create_hips( lower_torso_bones )
            # TODO: Add create tail

            if tail_bones:
                bones['tail'] = self.create_tail( tail_bones )

            # TEST
            bpy.ops.object.mode_set(mode ='EDIT')
            eb = self.obj.data.edit_bones

            self.parent_bones(      bones )
            self.constrain_bones(   bones )
            self.create_drivers(    bones )
            self.locks_and_widgets( bones )


        controls =  [ bones['neck']['ctrl'],  bones['neck']['ctrl_neck'] ]
        controls += [ bones['chest']['ctrl'], bones['hips']['ctrl']      ]
        controls += [ bones['pivot']['ctrl'] ]
        
        if 'tail' in bones.keys():
            controls += [ bones['tail']['ctrl'] ]

        # Create UI
        controls_string = ", ".join(["'" + x + "'" for x in controls])
        return [script % (
            controls_string, 
            bones['pivot']['ctrl'], 
            'head_follow',
            'neck_follow'
            )]

def add_parameters( params ):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """
    params.neck_pos = bpy.props.IntProperty(
        name        = 'neck_position',
        default     = 6,
        min         = 0,
        description = 'Neck start position'
    )

    params.pivot_pos = bpy.props.IntProperty(
        name         = 'pivot_position',
        default      = 3,
        min          = 0,
        description  = 'Position of the torso control and pivot point'
    )

    params.tail_pos = bpy.props.IntProperty(
        name        = 'tail_position',
        default     = 0,
        min         = 0,
        description = 'Where the tail starts (change from 0 to enable)'
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
    r.prop(params, "neck_pos")

    r = layout.row()
    r.prop(params, "pivot_pos")

    r = layout.row()
    r.prop(params, "tail_pos")

    r = layout.row()
    r.prop(params, "tweak_extra_layers")
    r.active = params.tweak_extra_layers
    
    col = r.column(align=True)
    row = col.row(align=True)

    for i in range(8):
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")

    row = col.row(align=True)

    for i in range(16,24):
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")

    col = r.column(align=True)
    row = col.row(align=True)

    for i in range(8,16):
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")

    row = col.row(align=True)

    for i in range(24,32):
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")

def create_sample(obj):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('spine')
    bone.head[:] = 0.0000, 0.0552, 1.0099
    bone.tail[:] = 0.0000, 0.0172, 1.1573
    bone.roll = 0.0000
    bone.use_connect = False
    bones['spine'] = bone.name
    bone = arm.edit_bones.new('spine.001')
    bone.head[:] = 0.0000, 0.0172, 1.1573
    bone.tail[:] = 0.0000, 0.0004, 1.2929
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['spine']]
    bones['spine.001'] = bone.name
    bone = arm.edit_bones.new('pelvis.L')
    bone.head[:] = 0.0000, 0.0552, 1.0099
    bone.tail[:] = 0.1112, -0.0451, 1.1533
    bone.roll = -1.0756
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine']]
    bones['pelvis.L'] = bone.name
    bone = arm.edit_bones.new('pelvis.R')
    bone.head[:] = -0.0000, 0.0552, 1.0099
    bone.tail[:] = -0.1112, -0.0451, 1.1533
    bone.roll = 1.0756
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine']]
    bones['pelvis.R'] = bone.name
    bone = arm.edit_bones.new('thigh.L')
    bone.head[:] = 0.0980, 0.0124, 1.0720
    bone.tail[:] = 0.0980, -0.0286, 0.5372
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine']]
    bones['thigh.L'] = bone.name
    bone = arm.edit_bones.new('thigh.R')
    bone.head[:] = -0.0980, 0.0124, 1.0720
    bone.tail[:] = -0.0980, -0.0286, 0.5372
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine']]
    bones['thigh.R'] = bone.name
    bone = arm.edit_bones.new('spine.002')
    bone.head[:] = 0.0000, 0.0004, 1.2929
    bone.tail[:] = 0.0000, 0.0059, 1.4657
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['spine.001']]
    bones['spine.002'] = bone.name
    bone = arm.edit_bones.new('shin.L')
    bone.head[:] = 0.0980, -0.0286, 0.5372
    bone.tail[:] = 0.0980, 0.0162, 0.0852
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['thigh.L']]
    bones['shin.L'] = bone.name
    bone = arm.edit_bones.new('shin.R')
    bone.head[:] = -0.0980, -0.0286, 0.5372
    bone.tail[:] = -0.0980, 0.0162, 0.0852
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['thigh.R']]
    bones['shin.R'] = bone.name
    bone = arm.edit_bones.new('spine.003')
    bone.head[:] = 0.0000, 0.0059, 1.4657
    bone.tail[:] = 0.0000, 0.0114, 1.6582
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['spine.002']]
    bones['spine.003'] = bone.name
    bone = arm.edit_bones.new('foot.L')
    bone.head[:] = 0.0980, 0.0162, 0.0852
    bone.tail[:] = 0.0980, -0.0934, 0.0167
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['shin.L']]
    bones['foot.L'] = bone.name
    bone = arm.edit_bones.new('foot.R')
    bone.head[:] = -0.0980, 0.0162, 0.0852
    bone.tail[:] = -0.0980, -0.0934, 0.0167
    bone.roll = -0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['shin.R']]
    bones['foot.R'] = bone.name
    bone = arm.edit_bones.new('spine.004')
    bone.head[:] = 0.0000, 0.0114, 1.6582
    bone.tail[:] = 0.0000, -0.0067, 1.7197
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['spine.003']]
    bones['spine.004'] = bone.name
    bone = arm.edit_bones.new('shoulder.L')
    bone.head[:] = 0.0183, -0.0684, 1.6051
    bone.tail[:] = 0.1694, 0.0205, 1.6050
    bone.roll = 0.0004
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine.003']]
    bones['shoulder.L'] = bone.name
    bone = arm.edit_bones.new('shoulder.R')
    bone.head[:] = -0.0183, -0.0684, 1.6051
    bone.tail[:] = -0.1694, 0.0205, 1.6050
    bone.roll = -0.0004
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine.003']]
    bones['shoulder.R'] = bone.name
    bone = arm.edit_bones.new('breast.L')
    bone.head[:] = 0.1184, 0.0485, 1.4596
    bone.tail[:] = 0.1184, -0.0907, 1.4596
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine.003']]
    bones['breast.L'] = bone.name
    bone = arm.edit_bones.new('breast.R')
    bone.head[:] = -0.1184, 0.0485, 1.4596
    bone.tail[:] = -0.1184, -0.0907, 1.4596
    bone.roll = -0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine.003']]
    bones['breast.R'] = bone.name
    bone = arm.edit_bones.new('toe.L')
    bone.head[:] = 0.0980, -0.0934, 0.0167
    bone.tail[:] = 0.0980, -0.1606, 0.0167
    bone.roll = -0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['foot.L']]
    bones['toe.L'] = bone.name
    bone = arm.edit_bones.new('heel.02.L')
    bone.head[:] = 0.0600, 0.0459, 0.0000
    bone.tail[:] = 0.1400, 0.0459, 0.0000
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['foot.L']]
    bones['heel.02.L'] = bone.name
    bone = arm.edit_bones.new('toe.R')
    bone.head[:] = -0.0980, -0.0934, 0.0167
    bone.tail[:] = -0.0980, -0.1606, 0.0167
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['foot.R']]
    bones['toe.R'] = bone.name
    bone = arm.edit_bones.new('heel.02.R')
    bone.head[:] = -0.0600, 0.0459, 0.0000
    bone.tail[:] = -0.1400, 0.0459, 0.0000
    bone.roll = -0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['foot.R']]
    bones['heel.02.R'] = bone.name
    bone = arm.edit_bones.new('spine.005')
    bone.head[:] = 0.0000, -0.0067, 1.7197
    bone.tail[:] = 0.0000, -0.0247, 1.7813
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['spine.004']]
    bones['spine.005'] = bone.name
    bone = arm.edit_bones.new('upper_arm.L')
    bone.head[:] = 0.1953, 0.0267, 1.5846
    bone.tail[:] = 0.4424, 0.0885, 1.4491
    bone.roll = 2.0724
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['shoulder.L']]
    bones['upper_arm.L'] = bone.name
    bone = arm.edit_bones.new('upper_arm.R')
    bone.head[:] = -0.1953, 0.0267, 1.5846
    bone.tail[:] = -0.4424, 0.0885, 1.4491
    bone.roll = -2.0724
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['shoulder.R']]
    bones['upper_arm.R'] = bone.name
    bone = arm.edit_bones.new('spine.006')
    bone.head[:] = 0.0000, -0.0247, 1.7813
    bone.tail[:] = 0.0000, -0.0247, 1.9796
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['spine.005']]
    bones['spine.006'] = bone.name
    bone = arm.edit_bones.new('forearm.L')
    bone.head[:] = 0.4424, 0.0885, 1.4491
    bone.tail[:] = 0.6594, 0.0492, 1.3061
    bone.roll = 2.1535
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['upper_arm.L']]
    bones['forearm.L'] = bone.name
    bone = arm.edit_bones.new('forearm.R')
    bone.head[:] = -0.4424, 0.0885, 1.4491
    bone.tail[:] = -0.6594, 0.0492, 1.3061
    bone.roll = -2.1535
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['upper_arm.R']]
    bones['forearm.R'] = bone.name
    bone = arm.edit_bones.new('face')
    bone.head[:] = 0.0000, -0.0247, 1.7813
    bone.tail[:] = 0.0000, -0.0247, 1.8725
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['spine.006']]
    bones['face'] = bone.name
    bone = arm.edit_bones.new('hand.L')
    bone.head[:] = 0.6594, 0.0492, 1.3061
    bone.tail[:] = 0.7234, 0.0412, 1.2585
    bone.roll = 2.2103
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['forearm.L']]
    bones['hand.L'] = bone.name
    bone = arm.edit_bones.new('hand.R')
    bone.head[:] = -0.6594, 0.0492, 1.3061
    bone.tail[:] = -0.7234, 0.0412, 1.2585
    bone.roll = -2.2103
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['forearm.R']]
    bones['hand.R'] = bone.name
    bone = arm.edit_bones.new('nose')
    bone.head[:] = 0.0006, -0.1536, 1.8978
    bone.tail[:] = 0.0006, -0.1834, 1.8589
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['nose'] = bone.name
    bone = arm.edit_bones.new('lip.T.L')
    bone.head[:] = -0.0000, -0.1710, 1.8140
    bone.tail[:] = 0.0195, -0.1656, 1.8146
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['lip.T.L'] = bone.name
    bone = arm.edit_bones.new('lip.B.L')
    bone.head[:] = -0.0000, -0.1667, 1.7978
    bone.tail[:] = 0.0185, -0.1585, 1.8028
    bone.roll = -0.0789
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['lip.B.L'] = bone.name
    bone = arm.edit_bones.new('jaw')
    bone.head[:] = 0.0006, -0.0945, 1.7439
    bone.tail[:] = 0.0006, -0.1519, 1.7392
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['jaw'] = bone.name
    bone = arm.edit_bones.new('ear.L')
    bone.head[:] = 0.0919, -0.0309, 1.8622
    bone.tail[:] = 0.0989, -0.0336, 1.9017
    bone.roll = -0.0324
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['ear.L'] = bone.name
    bone = arm.edit_bones.new('ear.R')
    bone.head[:] = -0.0919, -0.0309, 1.8622
    bone.tail[:] = -0.0989, -0.0336, 1.9017
    bone.roll = 0.0324
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['ear.R'] = bone.name
    bone = arm.edit_bones.new('lip.T.R')
    bone.head[:] = 0.0000, -0.1710, 1.8140
    bone.tail[:] = -0.0195, -0.1656, 1.8146
    bone.roll = -0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['lip.T.R'] = bone.name
    bone = arm.edit_bones.new('lip.B.R')
    bone.head[:] = 0.0000, -0.1667, 1.7978
    bone.tail[:] = -0.0185, -0.1585, 1.8028
    bone.roll = 0.0789
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['lip.B.R'] = bone.name
    bone = arm.edit_bones.new('brow.B.L')
    bone.head[:] = 0.0791, -0.1237, 1.9020
    bone.tail[:] = 0.0704, -0.1349, 1.9078
    bone.roll = 0.0412
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['brow.B.L'] = bone.name
    bone = arm.edit_bones.new('lid.T.L')
    bone.head[:] = 0.0768, -0.1218, 1.8947
    bone.tail[:] = 0.0678, -0.1356, 1.8995
    bone.roll = -0.2079
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['lid.T.L'] = bone.name
    bone = arm.edit_bones.new('brow.B.R')
    bone.head[:] = -0.0791, -0.1237, 1.9020
    bone.tail[:] = -0.0704, -0.1349, 1.9078
    bone.roll = -0.0412
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['brow.B.R'] = bone.name
    bone = arm.edit_bones.new('lid.T.R')
    bone.head[:] = -0.0768, -0.1218, 1.8947
    bone.tail[:] = -0.0678, -0.1356, 1.8995
    bone.roll = 0.2079
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['lid.T.R'] = bone.name
    bone = arm.edit_bones.new('forehead.L')
    bone.head[:] = 0.0168, -0.1325, 1.9704
    bone.tail[:] = 0.0215, -0.1546, 1.9144
    bone.roll = 1.4313
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['forehead.L'] = bone.name
    bone = arm.edit_bones.new('forehead.R')
    bone.head[:] = -0.0168, -0.1325, 1.9704
    bone.tail[:] = -0.0215, -0.1546, 1.9144
    bone.roll = -1.4313
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['forehead.R'] = bone.name
    bone = arm.edit_bones.new('eye.L')
    bone.head[:] = 0.0516, -0.1209, 1.8941
    bone.tail[:] = 0.0516, -0.1451, 1.8941
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['eye.L'] = bone.name
    bone = arm.edit_bones.new('eye.R')
    bone.head[:] = -0.0516, -0.1209, 1.8941
    bone.tail[:] = -0.0516, -0.1451, 1.8941
    bone.roll = -0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['eye.R'] = bone.name
    bone = arm.edit_bones.new('cheek.T.L')
    bone.head[:] = 0.0848, -0.0940, 1.8870
    bone.tail[:] = 0.0565, -0.1430, 1.8517
    bone.roll = -0.0096
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['cheek.T.L'] = bone.name
    bone = arm.edit_bones.new('cheek.T.R')
    bone.head[:] = -0.0848, -0.0940, 1.8870
    bone.tail[:] = -0.0565, -0.1430, 1.8517
    bone.roll = 0.0096
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['cheek.T.R'] = bone.name
    bone = arm.edit_bones.new('teeth.T')
    bone.head[:] = 0.0006, -0.1568, 1.8214
    bone.tail[:] = 0.0006, -0.1112, 1.8214
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['teeth.T'] = bone.name
    bone = arm.edit_bones.new('teeth.B')
    bone.head[:] = 0.0006, -0.1500, 1.7892
    bone.tail[:] = 0.0006, -0.1043, 1.7892
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['teeth.B'] = bone.name
    bone = arm.edit_bones.new('tongue')
    bone.head[:] = 0.0006, -0.1354, 1.7946
    bone.tail[:] = 0.0006, -0.1101, 1.8002
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['face']]
    bones['tongue'] = bone.name
    bone = arm.edit_bones.new('palm.01.L')
    bone.head[:] = 0.6921, 0.0224, 1.2882
    bone.tail[:] = 0.7464, 0.0051, 1.2482
    bone.roll = -2.4928
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.L']]
    bones['palm.01.L'] = bone.name
    bone = arm.edit_bones.new('palm.02.L')
    bone.head[:] = 0.6970, 0.0389, 1.2877
    bone.tail[:] = 0.7518, 0.0277, 1.2487
    bone.roll = -2.5274
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.L']]
    bones['palm.02.L'] = bone.name
    bone = arm.edit_bones.new('palm.03.L')
    bone.head[:] = 0.6963, 0.0545, 1.2874
    bone.tail[:] = 0.7540, 0.0521, 1.2482
    bone.roll = -2.5843
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.L']]
    bones['palm.03.L'] = bone.name
    bone = arm.edit_bones.new('palm.04.L')
    bone.head[:] = 0.6929, 0.0696, 1.2871
    bone.tail[:] = 0.7528, 0.0763, 1.2428
    bone.roll = -2.5155
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.L']]
    bones['palm.04.L'] = bone.name
    bone = arm.edit_bones.new('palm.01.R')
    bone.head[:] = -0.6921, 0.0224, 1.2882
    bone.tail[:] = -0.7464, 0.0051, 1.2482
    bone.roll = 2.4928
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.R']]
    bones['palm.01.R'] = bone.name
    bone = arm.edit_bones.new('palm.02.R')
    bone.head[:] = -0.6970, 0.0389, 1.2877
    bone.tail[:] = -0.7518, 0.0277, 1.2487
    bone.roll = 2.5274
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.R']]
    bones['palm.02.R'] = bone.name
    bone = arm.edit_bones.new('palm.03.R')
    bone.head[:] = -0.6963, 0.0544, 1.2874
    bone.tail[:] = -0.7540, 0.0521, 1.2482
    bone.roll = 2.5843
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.R']]
    bones['palm.03.R'] = bone.name
    bone = arm.edit_bones.new('palm.04.R')
    bone.head[:] = -0.6929, 0.0696, 1.2871
    bone.tail[:] = -0.7528, 0.0763, 1.2428
    bone.roll = 2.5155
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['hand.R']]
    bones['palm.04.R'] = bone.name
    bone = arm.edit_bones.new('nose.001')
    bone.head[:] = 0.0006, -0.1834, 1.8589
    bone.tail[:] = 0.0006, -0.1965, 1.8450
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['nose']]
    bones['nose.001'] = bone.name
    bone = arm.edit_bones.new('lip.T.L.001')
    bone.head[:] = 0.0195, -0.1656, 1.8146
    bone.tail[:] = 0.0352, -0.1494, 1.8074
    bone.roll = 0.0236
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lip.T.L']]
    bones['lip.T.L.001'] = bone.name
    bone = arm.edit_bones.new('lip.B.L.001')
    bone.head[:] = 0.0185, -0.1585, 1.8028
    bone.tail[:] = 0.0352, -0.1494, 1.8074
    bone.roll = 0.0731
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lip.B.L']]
    bones['lip.B.L.001'] = bone.name
    bone = arm.edit_bones.new('chin')
    bone.head[:] = 0.0006, -0.1519, 1.7392
    bone.tail[:] = 0.0006, -0.1634, 1.7692
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['jaw']]
    bones['chin'] = bone.name
    bone = arm.edit_bones.new('ear.L.001')
    bone.head[:] = 0.0989, -0.0336, 1.9017
    bone.tail[:] = 0.1200, -0.0088, 1.9074
    bone.roll = 0.0656
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.L']]
    bones['ear.L.001'] = bone.name
    bone = arm.edit_bones.new('ear.R.001')
    bone.head[:] = -0.0989, -0.0336, 1.9017
    bone.tail[:] = -0.1200, -0.0088, 1.9074
    bone.roll = -0.0656
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.R']]
    bones['ear.R.001'] = bone.name
    bone = arm.edit_bones.new('lip.T.R.001')
    bone.head[:] = -0.0195, -0.1656, 1.8146
    bone.tail[:] = -0.0352, -0.1494, 1.8074
    bone.roll = -0.0236
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lip.T.R']]
    bones['lip.T.R.001'] = bone.name
    bone = arm.edit_bones.new('lip.B.R.001')
    bone.head[:] = -0.0185, -0.1585, 1.8028
    bone.tail[:] = -0.0352, -0.1494, 1.8074
    bone.roll = -0.0731
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lip.B.R']]
    bones['lip.B.R.001'] = bone.name
    bone = arm.edit_bones.new('brow.B.L.001')
    bone.head[:] = 0.0704, -0.1349, 1.9078
    bone.tail[:] = 0.0577, -0.1427, 1.9093
    bone.roll = 0.0192
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.B.L']]
    bones['brow.B.L.001'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.001')
    bone.head[:] = 0.0678, -0.1356, 1.8995
    bone.tail[:] = 0.0550, -0.1436, 1.9022
    bone.roll = 0.1837
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.L']]
    bones['lid.T.L.001'] = bone.name
    bone = arm.edit_bones.new('brow.B.R.001')
    bone.head[:] = -0.0704, -0.1349, 1.9078
    bone.tail[:] = -0.0577, -0.1427, 1.9093
    bone.roll = -0.0192
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.B.R']]
    bones['brow.B.R.001'] = bone.name
    bone = arm.edit_bones.new('lid.T.R.001')
    bone.head[:] = -0.0678, -0.1356, 1.8995
    bone.tail[:] = -0.0550, -0.1436, 1.9022
    bone.roll = -0.1837
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.R']]
    bones['lid.T.R.001'] = bone.name
    bone = arm.edit_bones.new('forehead.L.001')
    bone.head[:] = 0.0479, -0.1174, 1.9756
    bone.tail[:] = 0.0588, -0.1421, 1.9255
    bone.roll = 0.9928
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['forehead.L']]
    bones['forehead.L.001'] = bone.name
    bone = arm.edit_bones.new('forehead.R.001')
    bone.head[:] = -0.0479, -0.1174, 1.9756
    bone.tail[:] = -0.0588, -0.1421, 1.9255
    bone.roll = -0.9928
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['forehead.R']]
    bones['forehead.R.001'] = bone.name
    bone = arm.edit_bones.new('cheek.T.L.001')
    bone.head[:] = 0.0565, -0.1430, 1.8517
    bone.tail[:] = 0.0188, -0.1448, 1.8822
    bone.roll = 0.1387
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.T.L']]
    bones['cheek.T.L.001'] = bone.name
    bone = arm.edit_bones.new('cheek.T.R.001')
    bone.head[:] = -0.0565, -0.1430, 1.8517
    bone.tail[:] = -0.0188, -0.1448, 1.8822
    bone.roll = -0.1387
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.T.R']]
    bones['cheek.T.R.001'] = bone.name
    bone = arm.edit_bones.new('tongue.001')
    bone.head[:] = 0.0006, -0.1101, 1.8002
    bone.tail[:] = 0.0006, -0.0761, 1.7949
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['tongue']]
    bones['tongue.001'] = bone.name
    bone = arm.edit_bones.new('f_index.01.L')
    bone.head[:] = 0.7464, 0.0051, 1.2482
    bone.tail[:] = 0.7718, 0.0013, 1.2112
    bone.roll = -2.0315
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.01.L']]
    bones['f_index.01.L'] = bone.name
    bone = arm.edit_bones.new('thumb.01.L')
    bone.head[:] = 0.6705, 0.0214, 1.2738
    bone.tail[:] = 0.6857, 0.0015, 1.2404
    bone.roll = -0.1587
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.01.L']]
    bones['thumb.01.L'] = bone.name
    bone = arm.edit_bones.new('f_middle.01.L')
    bone.head[:] = 0.7518, 0.0277, 1.2487
    bone.tail[:] = 0.7762, 0.0234, 1.2058
    bone.roll = -2.0067
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.02.L']]
    bones['f_middle.01.L'] = bone.name
    bone = arm.edit_bones.new('f_ring.01.L')
    bone.head[:] = 0.7540, 0.0521, 1.2482
    bone.tail[:] = 0.7715, 0.0499, 1.2070
    bone.roll = -2.0082
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.03.L']]
    bones['f_ring.01.L'] = bone.name
    bone = arm.edit_bones.new('f_pinky.01.L')
    bone.head[:] = 0.7528, 0.0763, 1.2428
    bone.tail[:] = 0.7589, 0.0765, 1.2156
    bone.roll = -1.9749
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.04.L']]
    bones['f_pinky.01.L'] = bone.name
    bone = arm.edit_bones.new('f_index.01.R')
    bone.head[:] = -0.7464, 0.0051, 1.2482
    bone.tail[:] = -0.7718, 0.0012, 1.2112
    bone.roll = 2.0315
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.01.R']]
    bones['f_index.01.R'] = bone.name
    bone = arm.edit_bones.new('thumb.01.R')
    bone.head[:] = -0.6705, 0.0214, 1.2738
    bone.tail[:] = -0.6857, 0.0015, 1.2404
    bone.roll = 0.1587
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.01.R']]
    bones['thumb.01.R'] = bone.name
    bone = arm.edit_bones.new('f_middle.01.R')
    bone.head[:] = -0.7518, 0.0277, 1.2487
    bone.tail[:] = -0.7762, 0.0233, 1.2058
    bone.roll = 2.0067
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.02.R']]
    bones['f_middle.01.R'] = bone.name
    bone = arm.edit_bones.new('f_ring.01.R')
    bone.head[:] = -0.7540, 0.0521, 1.2482
    bone.tail[:] = -0.7715, 0.0499, 1.2070
    bone.roll = 2.0082
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.03.R']]
    bones['f_ring.01.R'] = bone.name
    bone = arm.edit_bones.new('f_pinky.01.R')
    bone.head[:] = -0.7528, 0.0763, 1.2428
    bone.tail[:] = -0.7589, 0.0765, 1.2156
    bone.roll = 1.9749
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['palm.04.R']]
    bones['f_pinky.01.R'] = bone.name
    bone = arm.edit_bones.new('nose.002')
    bone.head[:] = 0.0006, -0.1965, 1.8450
    bone.tail[:] = 0.0006, -0.1854, 1.8402
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['nose.001']]
    bones['nose.002'] = bone.name
    bone = arm.edit_bones.new('chin.001')
    bone.head[:] = 0.0006, -0.1634, 1.7692
    bone.tail[:] = 0.0006, -0.1599, 1.7909
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['chin']]
    bones['chin.001'] = bone.name
    bone = arm.edit_bones.new('ear.L.002')
    bone.head[:] = 0.1200, -0.0088, 1.9074
    bone.tail[:] = 0.1206, -0.0101, 1.8695
    bone.roll = -0.0265
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.L.001']]
    bones['ear.L.002'] = bone.name
    bone = arm.edit_bones.new('ear.R.002')
    bone.head[:] = -0.1200, -0.0088, 1.9074
    bone.tail[:] = -0.1206, -0.0101, 1.8695
    bone.roll = 0.0265
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.R.001']]
    bones['ear.R.002'] = bone.name
    bone = arm.edit_bones.new('brow.B.L.002')
    bone.head[:] = 0.0577, -0.1427, 1.9093
    bone.tail[:] = 0.0388, -0.1418, 1.9069
    bone.roll = 0.0847
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.B.L.001']]
    bones['brow.B.L.002'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.002')
    bone.head[:] = 0.0550, -0.1436, 1.9022
    bone.tail[:] = 0.0425, -0.1427, 1.8987
    bone.roll = -0.0940
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.L.001']]
    bones['lid.T.L.002'] = bone.name
    bone = arm.edit_bones.new('brow.B.R.002')
    bone.head[:] = -0.0577, -0.1427, 1.9093
    bone.tail[:] = -0.0388, -0.1418, 1.9069
    bone.roll = -0.0847
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.B.R.001']]
    bones['brow.B.R.002'] = bone.name
    bone = arm.edit_bones.new('lid.T.R.002')
    bone.head[:] = -0.0550, -0.1436, 1.9022
    bone.tail[:] = -0.0425, -0.1427, 1.8987
    bone.roll = 0.0940
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.R.001']]
    bones['lid.T.R.002'] = bone.name
    bone = arm.edit_bones.new('forehead.L.002')
    bone.head[:] = 0.0719, -0.0940, 1.9717
    bone.tail[:] = 0.0830, -0.1213, 1.9164
    bone.roll = 0.4509
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['forehead.L.001']]
    bones['forehead.L.002'] = bone.name
    bone = arm.edit_bones.new('forehead.R.002')
    bone.head[:] = -0.0719, -0.0940, 1.9717
    bone.tail[:] = -0.0830, -0.1213, 1.9164
    bone.roll = -0.4509
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['forehead.R.001']]
    bones['forehead.R.002'] = bone.name
    bone = arm.edit_bones.new('nose.L')
    bone.head[:] = 0.0188, -0.1448, 1.8822
    bone.tail[:] = 0.0176, -0.1627, 1.8429
    bone.roll = 0.0997
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.T.L.001']]
    bones['nose.L'] = bone.name
    bone = arm.edit_bones.new('nose.R')
    bone.head[:] = -0.0188, -0.1448, 1.8822
    bone.tail[:] = -0.0176, -0.1627, 1.8429
    bone.roll = -0.0997
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.T.R.001']]
    bones['nose.R'] = bone.name
    bone = arm.edit_bones.new('tongue.002')
    bone.head[:] = 0.0006, -0.0761, 1.7949
    bone.tail[:] = 0.0006, -0.0538, 1.7673
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['tongue.001']]
    bones['tongue.002'] = bone.name
    bone = arm.edit_bones.new('f_index.02.L')
    bone.head[:] = 0.7718, 0.0013, 1.2112
    bone.tail[:] = 0.7840, -0.0003, 1.1858
    bone.roll = -1.8799
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_index.01.L']]
    bones['f_index.02.L'] = bone.name
    bone = arm.edit_bones.new('thumb.02.L')
    bone.head[:] = 0.6857, 0.0015, 1.2404
    bone.tail[:] = 0.7056, -0.0057, 1.2145
    bone.roll = -0.4798
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['thumb.01.L']]
    bones['thumb.02.L'] = bone.name
    bone = arm.edit_bones.new('f_middle.02.L')
    bone.head[:] = 0.7762, 0.0234, 1.2058
    bone.tail[:] = 0.7851, 0.0218, 1.1749
    bone.roll = -1.8283
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_middle.01.L']]
    bones['f_middle.02.L'] = bone.name
    bone = arm.edit_bones.new('f_ring.02.L')
    bone.head[:] = 0.7715, 0.0499, 1.2070
    bone.tail[:] = 0.7794, 0.0494, 1.1762
    bone.roll = -1.8946
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_ring.01.L']]
    bones['f_ring.02.L'] = bone.name
    bone = arm.edit_bones.new('f_pinky.02.L')
    bone.head[:] = 0.7589, 0.0765, 1.2156
    bone.tail[:] = 0.7618, 0.0770, 1.1932
    bone.roll = -1.9059
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_pinky.01.L']]
    bones['f_pinky.02.L'] = bone.name
    bone = arm.edit_bones.new('f_index.02.R')
    bone.head[:] = -0.7718, 0.0012, 1.2112
    bone.tail[:] = -0.7840, -0.0003, 1.1858
    bone.roll = 1.8799
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_index.01.R']]
    bones['f_index.02.R'] = bone.name
    bone = arm.edit_bones.new('thumb.02.R')
    bone.head[:] = -0.6857, 0.0015, 1.2404
    bone.tail[:] = -0.7056, -0.0057, 1.2145
    bone.roll = 0.4798
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['thumb.01.R']]
    bones['thumb.02.R'] = bone.name
    bone = arm.edit_bones.new('f_middle.02.R')
    bone.head[:] = -0.7762, 0.0233, 1.2058
    bone.tail[:] = -0.7851, 0.0218, 1.1749
    bone.roll = 1.8283
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_middle.01.R']]
    bones['f_middle.02.R'] = bone.name
    bone = arm.edit_bones.new('f_ring.02.R')
    bone.head[:] = -0.7715, 0.0499, 1.2070
    bone.tail[:] = -0.7794, 0.0494, 1.1762
    bone.roll = 1.8946
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_ring.01.R']]
    bones['f_ring.02.R'] = bone.name
    bone = arm.edit_bones.new('f_pinky.02.R')
    bone.head[:] = -0.7589, 0.0765, 1.2156
    bone.tail[:] = -0.7618, 0.0770, 1.1932
    bone.roll = 1.9059
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_pinky.01.R']]
    bones['f_pinky.02.R'] = bone.name
    bone = arm.edit_bones.new('nose.003')
    bone.head[:] = 0.0006, -0.1854, 1.8402
    bone.tail[:] = 0.0006, -0.1706, 1.8393
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['nose.002']]
    bones['nose.003'] = bone.name
    bone = arm.edit_bones.new('ear.L.003')
    bone.head[:] = 0.1206, -0.0101, 1.8695
    bone.tail[:] = 0.1010, -0.0347, 1.8422
    bone.roll = 0.3033
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.L.002']]
    bones['ear.L.003'] = bone.name
    bone = arm.edit_bones.new('ear.R.003')
    bone.head[:] = -0.1206, -0.0101, 1.8695
    bone.tail[:] = -0.1010, -0.0347, 1.8422
    bone.roll = -0.3033
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.R.002']]
    bones['ear.R.003'] = bone.name
    bone = arm.edit_bones.new('brow.B.L.003')
    bone.head[:] = 0.0388, -0.1418, 1.9069
    bone.tail[:] = 0.0221, -0.1397, 1.8950
    bone.roll = 0.1405
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.B.L.002']]
    bones['brow.B.L.003'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.003')
    bone.head[:] = 0.0425, -0.1427, 1.8987
    bone.tail[:] = 0.0262, -0.1418, 1.8891
    bone.roll = 0.2194
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.L.002']]
    bones['lid.T.L.003'] = bone.name
    bone = arm.edit_bones.new('brow.B.R.003')
    bone.head[:] = -0.0388, -0.1418, 1.9069
    bone.tail[:] = -0.0221, -0.1397, 1.8950
    bone.roll = -0.1405
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.B.R.002']]
    bones['brow.B.R.003'] = bone.name
    bone = arm.edit_bones.new('lid.T.R.003')
    bone.head[:] = -0.0425, -0.1427, 1.8987
    bone.tail[:] = -0.0262, -0.1418, 1.8891
    bone.roll = -0.2194
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.R.002']]
    bones['lid.T.R.003'] = bone.name
    bone = arm.edit_bones.new('temple.L')
    bone.head[:] = 0.0873, -0.0597, 1.9523
    bone.tail[:] = 0.0926, -0.0625, 1.8738
    bone.roll = -0.0913
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['forehead.L.002']]
    bones['temple.L'] = bone.name
    bone = arm.edit_bones.new('temple.R')
    bone.head[:] = -0.0873, -0.0597, 1.9523
    bone.tail[:] = -0.0926, -0.0625, 1.8738
    bone.roll = 0.0913
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['forehead.R.002']]
    bones['temple.R'] = bone.name
    bone = arm.edit_bones.new('nose.L.001')
    bone.head[:] = 0.0176, -0.1627, 1.8429
    bone.tail[:] = 0.0006, -0.1965, 1.8450
    bone.roll = 0.1070
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['nose.L']]
    bones['nose.L.001'] = bone.name
    bone = arm.edit_bones.new('nose.R.001')
    bone.head[:] = -0.0176, -0.1627, 1.8429
    bone.tail[:] = -0.0006, -0.1965, 1.8450
    bone.roll = -0.1070
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['nose.R']]
    bones['nose.R.001'] = bone.name
    bone = arm.edit_bones.new('f_index.03.L')
    bone.head[:] = 0.7840, -0.0003, 1.1858
    bone.tail[:] = 0.7892, 0.0006, 1.1636
    bone.roll = -1.6760
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_index.02.L']]
    bones['f_index.03.L'] = bone.name
    bone = arm.edit_bones.new('thumb.03.L')
    bone.head[:] = 0.7056, -0.0057, 1.2145
    bone.tail[:] = 0.7194, -0.0098, 1.1995
    bone.roll = -0.5826
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['thumb.02.L']]
    bones['thumb.03.L'] = bone.name
    bone = arm.edit_bones.new('f_middle.03.L')
    bone.head[:] = 0.7851, 0.0218, 1.1749
    bone.tail[:] = 0.7888, 0.0216, 1.1525
    bone.roll = -1.7483
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_middle.02.L']]
    bones['f_middle.03.L'] = bone.name
    bone = arm.edit_bones.new('f_ring.03.L')
    bone.head[:] = 0.7794, 0.0494, 1.1762
    bone.tail[:] = 0.7781, 0.0498, 1.1577
    bone.roll = -1.6582
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_ring.02.L']]
    bones['f_ring.03.L'] = bone.name
    bone = arm.edit_bones.new('f_pinky.03.L')
    bone.head[:] = 0.7618, 0.0770, 1.1932
    bone.tail[:] = 0.7611, 0.0772, 1.1782
    bone.roll = -1.7639
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_pinky.02.L']]
    bones['f_pinky.03.L'] = bone.name
    bone = arm.edit_bones.new('f_index.03.R')
    bone.head[:] = -0.7840, -0.0003, 1.1858
    bone.tail[:] = -0.7892, 0.0006, 1.1636
    bone.roll = 1.6760
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_index.02.R']]
    bones['f_index.03.R'] = bone.name
    bone = arm.edit_bones.new('thumb.03.R')
    bone.head[:] = -0.7056, -0.0057, 1.2145
    bone.tail[:] = -0.7194, -0.0098, 1.1995
    bone.roll = 0.5826
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['thumb.02.R']]
    bones['thumb.03.R'] = bone.name
    bone = arm.edit_bones.new('f_middle.03.R')
    bone.head[:] = -0.7851, 0.0218, 1.1749
    bone.tail[:] = -0.7888, 0.0216, 1.1525
    bone.roll = 1.7483
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_middle.02.R']]
    bones['f_middle.03.R'] = bone.name
    bone = arm.edit_bones.new('f_ring.03.R')
    bone.head[:] = -0.7794, 0.0494, 1.1762
    bone.tail[:] = -0.7781, 0.0498, 1.1577
    bone.roll = 1.6582
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_ring.02.R']]
    bones['f_ring.03.R'] = bone.name
    bone = arm.edit_bones.new('f_pinky.03.R')
    bone.head[:] = -0.7618, 0.0770, 1.1932
    bone.tail[:] = -0.7611, 0.0772, 1.1782
    bone.roll = 1.7639
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['f_pinky.02.R']]
    bones['f_pinky.03.R'] = bone.name
    bone = arm.edit_bones.new('nose.004')
    bone.head[:] = 0.0006, -0.1706, 1.8393
    bone.tail[:] = 0.0006, -0.1698, 1.8244
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['nose.003']]
    bones['nose.004'] = bone.name
    bone = arm.edit_bones.new('ear.L.004')
    bone.head[:] = 0.1010, -0.0347, 1.8422
    bone.tail[:] = 0.0919, -0.0309, 1.8622
    bone.roll = 0.1518
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.L.003']]
    bones['ear.L.004'] = bone.name
    bone = arm.edit_bones.new('ear.R.004')
    bone.head[:] = -0.1010, -0.0347, 1.8422
    bone.tail[:] = -0.0919, -0.0309, 1.8622
    bone.roll = -0.1518
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['ear.R.003']]
    bones['ear.R.004'] = bone.name
    bone = arm.edit_bones.new('lid.B.L')
    bone.head[:] = 0.0262, -0.1418, 1.8891
    bone.tail[:] = 0.0393, -0.1425, 1.8854
    bone.roll = 0.0756
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.L.003']]
    bones['lid.B.L'] = bone.name
    bone = arm.edit_bones.new('lid.B.R')
    bone.head[:] = -0.0262, -0.1418, 1.8891
    bone.tail[:] = -0.0393, -0.1425, 1.8854
    bone.roll = -0.0756
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.R.003']]
    bones['lid.B.R'] = bone.name
    bone = arm.edit_bones.new('jaw.L')
    bone.head[:] = 0.0926, -0.0625, 1.8738
    bone.tail[:] = 0.0783, -0.0689, 1.7975
    bone.roll = -0.0899
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['temple.L']]
    bones['jaw.L'] = bone.name
    bone = arm.edit_bones.new('jaw.R')
    bone.head[:] = -0.0926, -0.0625, 1.8738
    bone.tail[:] = -0.0783, -0.0689, 1.7975
    bone.roll = 0.0899
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['temple.R']]
    bones['jaw.R'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.001')
    bone.head[:] = 0.0393, -0.1425, 1.8854
    bone.tail[:] = 0.0553, -0.1418, 1.8833
    bone.roll = 0.1015
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.L']]
    bones['lid.B.L.001'] = bone.name
    bone = arm.edit_bones.new('lid.B.R.001')
    bone.head[:] = -0.0393, -0.1425, 1.8854
    bone.tail[:] = -0.0553, -0.1418, 1.8833
    bone.roll = -0.1015
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.R']]
    bones['lid.B.R.001'] = bone.name
    bone = arm.edit_bones.new('jaw.L.001')
    bone.head[:] = 0.0783, -0.0689, 1.7975
    bone.tail[:] = 0.0387, -0.1315, 1.7536
    bone.roll = 0.1223
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['jaw.L']]
    bones['jaw.L.001'] = bone.name
    bone = arm.edit_bones.new('jaw.R.001')
    bone.head[:] = -0.0783, -0.0689, 1.7975
    bone.tail[:] = -0.0387, -0.1315, 1.7536
    bone.roll = -0.1223
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['jaw.R']]
    bones['jaw.R.001'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.002')
    bone.head[:] = 0.0553, -0.1418, 1.8833
    bone.tail[:] = 0.0694, -0.1351, 1.8889
    bone.roll = -0.0748
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.L.001']]
    bones['lid.B.L.002'] = bone.name
    bone = arm.edit_bones.new('lid.B.R.002')
    bone.head[:] = -0.0553, -0.1418, 1.8833
    bone.tail[:] = -0.0694, -0.1351, 1.8889
    bone.roll = 0.0748
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.R.001']]
    bones['lid.B.R.002'] = bone.name
    bone = arm.edit_bones.new('chin.L')
    bone.head[:] = 0.0387, -0.1315, 1.7536
    bone.tail[:] = 0.0352, -0.1494, 1.8074
    bone.roll = -0.2078
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['jaw.L.001']]
    bones['chin.L'] = bone.name
    bone = arm.edit_bones.new('chin.R')
    bone.head[:] = -0.0387, -0.1315, 1.7536
    bone.tail[:] = -0.0352, -0.1494, 1.8074
    bone.roll = 0.2078
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['jaw.R.001']]
    bones['chin.R'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.003')
    bone.head[:] = 0.0694, -0.1351, 1.8889
    bone.tail[:] = 0.0768, -0.1218, 1.8947
    bone.roll = -0.0085
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.L.002']]
    bones['lid.B.L.003'] = bone.name
    bone = arm.edit_bones.new('lid.B.R.003')
    bone.head[:] = -0.0694, -0.1351, 1.8889
    bone.tail[:] = -0.0768, -0.1218, 1.8947
    bone.roll = 0.0085
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.R.002']]
    bones['lid.B.R.003'] = bone.name
    bone = arm.edit_bones.new('cheek.B.L')
    bone.head[:] = 0.0352, -0.1494, 1.8074
    bone.tail[:] = 0.0736, -0.1216, 1.8243
    bone.roll = 0.0015
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['chin.L']]
    bones['cheek.B.L'] = bone.name
    bone = arm.edit_bones.new('cheek.B.R')
    bone.head[:] = -0.0352, -0.1494, 1.8074
    bone.tail[:] = -0.0736, -0.1216, 1.8243
    bone.roll = -0.0015
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['chin.R']]
    bones['cheek.B.R'] = bone.name
    bone = arm.edit_bones.new('cheek.B.L.001')
    bone.head[:] = 0.0736, -0.1216, 1.8243
    bone.tail[:] = 0.0848, -0.0940, 1.8870
    bone.roll = -0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.B.L']]
    bones['cheek.B.L.001'] = bone.name
    bone = arm.edit_bones.new('cheek.B.R.001')
    bone.head[:] = -0.0736, -0.1216, 1.8243
    bone.tail[:] = -0.0848, -0.0940, 1.8870
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.B.R']]
    bones['cheek.B.R.001'] = bone.name
    bone = arm.edit_bones.new('brow.T.L')
    bone.head[:] = 0.0848, -0.0940, 1.8870
    bone.tail[:] = 0.0830, -0.1213, 1.9164
    bone.roll = 0.1990
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.B.L.001']]
    bones['brow.T.L'] = bone.name
    bone = arm.edit_bones.new('brow.T.R')
    bone.head[:] = -0.0848, -0.0940, 1.8870
    bone.tail[:] = -0.0830, -0.1213, 1.9164
    bone.roll = -0.1990
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['cheek.B.R.001']]
    bones['brow.T.R'] = bone.name
    bone = arm.edit_bones.new('brow.T.L.001')
    bone.head[:] = 0.0830, -0.1213, 1.9164
    bone.tail[:] = 0.0588, -0.1421, 1.9255
    bone.roll = 0.2372
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.T.L']]
    bones['brow.T.L.001'] = bone.name
    bone = arm.edit_bones.new('brow.T.R.001')
    bone.head[:] = -0.0830, -0.1213, 1.9164
    bone.tail[:] = -0.0588, -0.1421, 1.9255
    bone.roll = -0.2372
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.T.R']]
    bones['brow.T.R.001'] = bone.name
    bone = arm.edit_bones.new('brow.T.L.002')
    bone.head[:] = 0.0588, -0.1421, 1.9255
    bone.tail[:] = 0.0215, -0.1546, 1.9144
    bone.roll = 0.0724
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.T.L.001']]
    bones['brow.T.L.002'] = bone.name
    bone = arm.edit_bones.new('brow.T.R.002')
    bone.head[:] = -0.0588, -0.1421, 1.9255
    bone.tail[:] = -0.0215, -0.1546, 1.9144
    bone.roll = -0.0724
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.T.R.001']]
    bones['brow.T.R.002'] = bone.name
    bone = arm.edit_bones.new('brow.T.L.003')
    bone.head[:] = 0.0215, -0.1546, 1.9144
    bone.tail[:] = 0.0004, -0.1536, 1.8978
    bone.roll = -0.0423
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.T.L.002']]
    bones['brow.T.L.003'] = bone.name
    bone = arm.edit_bones.new('brow.T.R.003')
    bone.head[:] = -0.0215, -0.1546, 1.9144
    bone.tail[:] = -0.0004, -0.1536, 1.8978
    bone.roll = 0.0423
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['brow.T.R.002']]
    bones['brow.T.R.003'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['spine']]
    pbone.rigify_type = 'pitchipoy.super_torso_turbo'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.chain_bone_controls = "1, 2, 3"
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.neck_pos = 5
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_layers = [False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['spine.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['pelvis.L']]
    pbone.rigify_type = 'basic.copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    try:
        pbone.rigify_parameters.make_control = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['pelvis.R']]
    pbone.rigify_type = 'basic.copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    try:
        pbone.rigify_parameters.make_control = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['thigh.L']]
    pbone.rigify_type = 'pitchipoy.limbs.super_limb'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_ik_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.ik_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.separate_hose_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.hose_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.limb_type = "leg"
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.fk_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['thigh.R']]
    pbone.rigify_type = 'pitchipoy.limbs.super_limb'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_ik_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.ik_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.separate_hose_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.hose_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.fk_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.limb_type = "leg"
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['spine.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['shin.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['shin.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['spine.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['foot.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['foot.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['spine.004']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['shoulder.L']]
    pbone.rigify_type = 'basic.copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['shoulder.R']]
    pbone.rigify_type = 'basic.copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['breast.L']]
    pbone.rigify_type = 'pitchipoy.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['breast.R']]
    pbone.rigify_type = 'pitchipoy.super_copy'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['toe.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['heel.02.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['toe.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['heel.02.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['spine.005']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['upper_arm.L']]
    pbone.rigify_type = 'pitchipoy.limbs.super_limb'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_ik_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.ik_layers = [False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.separate_hose_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.hose_layers = [False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_layers = [False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.fk_layers = [False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['upper_arm.R']]
    pbone.rigify_type = 'pitchipoy.limbs.super_limb'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_ik_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.ik_layers = [False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.separate_hose_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.hose_layers = [False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_layers = [False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.fk_layers = [False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['spine.006']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forearm.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forearm.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['face']]
    pbone.rigify_type = 'pitchipoy.super_face'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.secondary_layers = [False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['hand.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['hand.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forehead.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forehead.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['eye.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['eye.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['teeth.T']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['teeth.B']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['tongue']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['palm.01.L']]
    pbone.rigify_type = 'palm'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['palm.02.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['palm.03.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['palm.04.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['palm.01.R']]
    pbone.rigify_type = 'palm'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['palm.02.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['palm.03.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['palm.04.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'YXZ'
    pbone = obj.pose.bones[bones['nose.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forehead.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forehead.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.T.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['tongue.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_index.01.L']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['thumb.01.L']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_middle.01.L']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_ring.01.L']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_pinky.01.L']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_index.01.R']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['thumb.01.R']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_middle.01.R']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_ring.01.R']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['f_pinky.01.R']]
    pbone.rigify_type = 'pitchipoy.simple_tentacle'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.separate_extra_layers = True
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.extra_layers = [False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.tweak_extra_layers = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['nose.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forehead.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['forehead.R.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['tongue.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_index.02.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['thumb.02.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_middle.02.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_ring.02.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_pinky.02.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_index.02.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['thumb.02.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_middle.02.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_ring.02.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_pinky.02.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.L.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.B.R.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.R.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['temple.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['temple.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_index.03.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['thumb.03.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_middle.03.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_ring.03.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_pinky.03.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_index.03.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['thumb.03.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_middle.03.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_ring.03.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['f_pinky.03.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['nose.004']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.L.004']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['ear.R.004']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['jaw.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['chin.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.R.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['cheek.B.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.L.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['brow.T.R.003']]
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
