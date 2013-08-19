import bpy
from mathutils   import Vector
from ...utils    import copy_bone, flip_bone, put_bone, org
from ...utils    import strip_org, make_deformer_name, connected_children_names 
from ...utils    import create_circle_widget, create_sphere_widget, create_widget
from ...utils    import MetarigError, make_mechanism_name, create_cube_widget
from rna_prop_ui import rna_idprop_ui_prop_get
from math        import trunc

def orient_bone( cls, eb, axis, scale, reverse = False ):
    v = Vector((0,0,0))
   
    setattr(v,axis,scale)

    if reverse:
        tail_vec = v * cls.obj.matrix_world
        eb.head[:] = eb.tail
        eb.tail[:] = eb.head + tail_vec     
    else:
        tail_vec = v * cls.obj.matrix_world
        eb.tail[:] = eb.head + tail_vec


def make_constraint( cls, bone, constraint ):
    bpy.ops.object.mode_set(mode = 'OBJECT')
    pb = cls.obj.pose.bones

    owner_pb     = pb[bone]
    const        = owner_pb.constraints.new( constraint['constraint'] )
    const.target = cls.obj

    # filter contraint props to those that actually exist in the currnet 
    # type of constraint, then assign values to each
    for p in [ k for k in constraint.keys() if k in dir(const) ]:
        setattr( const, p, constraint[p] )


class Limb:
    def __init__(self, obj, bone_name, params):
        """ Initialize torso rig and key rig properties """
        self.obj       = obj
        self.params    = params
        self.org_bones = list(
            [bone_name] + connected_children_names(obj, bone_name)
            )[:2]  # The basic limb is the first 3 bones

        self.segments = params.segments

        # Assign values to tweak/FK layers props if opted by user
        if params.tweak_extra_layers:
            self.tweak_layers = list(params.tweak_layers)
        else:
            self.tweak_layers = None

        if params.fk_extra_layers:
            self.fk_layers = list(params.fk_layers)
        else:
            self.fk_layers = None

    def create_tweak( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        tweaks         = {}        
        tweaks['ctrl'] = []
        tweaks['mch' ] = []

        # Create and parent mch and ctrl tweaks
        for i,org in enumerate(org_bones):
            if i < len(org_bones) - 1:
                # Create segments if specified
                for j in range( self.segments ):
                    # MCH
                    mch = copy_bone(
                        self.obj,
                        org,
                        make_mechanism_name( strip_org(org) )
                    )
                    
                    eb[ mch ].length /= self.segments * 4

                    # CTRL
                    ctrl = copy_bone(
                        self.obj,
                        org,
                        strip_org(org)
                    )
                    
                    eb[ ctrl ].length /= self.segments * 2

                    # If we have more than one segments, place the head of the 
                    # 2nd and onwards at the correct position
                    if j > 0:
                        put_bone(
                            self.obj, 
                            mch,
                            eb[org].head + i * eb[org].length / self.segments
                        )

                        put_bone(
                            self.obj, 
                            ctrl,
                            eb[org].head + i * eb[org].length / self.segments
                        )

                    tweaks['ctrl'] += [ ctrl ]
                    tweaks['mch' ] += [ mch  ]

                    # Parenting the tweak ctrls to mchs
                    eb[ mch  ].parent = eb[ org ]
                    eb[ ctrl ].parent = eb[ mch ]

            else: # Last limb bone - is not subdivided        
                mch = make_mechanism_name( strip_org(org) )
                mch = copy_bone( self.obj, org_bones[i-1], mch )
                eb[ mch ].length = eb[org].length / 4
                put_bone(
                    self.obj, 
                    mch,
                    eb[org_bones[i-1]].tail
                )                        
 
                ctrl = strip_org(org)
                ctrl = copy_bone( self.obj, org, ctrl )
                eb[ ctrl ].length = eb[org].length / 2 

                tweaks['mch']  += [ mch  ]
                tweaks['ctrl'] += [ ctrl ]
        
                # Parenting the tweak ctrls to mchs
                eb[ mch  ].parent = eb[ org ]
                eb[ ctrl ].parent = eb[ mch ]

        # Contraints
        for i,b in enumerate( tweaks['mch'] ):
            first  = 0
            middle = trunc( len( tweaks['mch'] ) / 2 )
            last   = len( tweaks['mch'] ) - 1

            if i == first or i == middle or i == last:
                make_constraint( self, b, {
                    'constraint'  : 'COPY_SCALE',
                    'subtarget'   : self.obj.pose.bones[0] # root
                })
            else:
                targets = []
                if i < trunc( len( tweaks['mch'] ) / 2 ):
                    targets = [first,middle]
                else:
                    targets = [middle,last]

                # Use copy transforms constraints to position each bone
                # exactly in the location respective to its index (between
                # the two edges)
                make_constraint( self, b, {
                    'constraint'  : 'COPY_TRANSFORMS',
                    'subtarget'   : tweaks['ctrl'][targets[0]]
                })
                make_constraint( self, b, {
                    'constraint'  : 'COPY_TRANSFORMS',
                    'subtarget'   : tweaks['ctrl'][targets[1]],
                    'influence'   : i / self.segments
                })
                make_constraint( self, d, {
                    'constraint'  : 'DAMPED_TRACK',
                    'subtarget'   : tweaks['ctrl'][i+1],
                })                

        # Ctrl bones Locks and Widgets
        pb = self.obj.pose.bones
        for t in tweaks['ctrl']:
            pb[t].lock_rotation = True, False, True
            pb[t].lock_scale    = False, True, False

            create_sphere_widget(self.obj, t, bone_transform_name=None)
            
            if self.tweak_layers:
                pb[t].bone.layers = self.tweak_layers 
        
        return tweaks


    def create_def( self, tweaks ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        def_bones = []
        for i,org in enumerate(org_bones):
            if i < len(org_bones) - 1:
                # Create segments if specified
                for j in range( self.segments ):
                    def_name = copy_bone(
                        self.obj,
                        org,
                        make_deformer_name( strip_org(org) )
                    )
                    
                    eb[ def_name ].length /= self.segments

                    # If we have more than one segments, place the 2nd and
                    # onwards on the tail of the previous bone
                    if j > 0:
                         put_bone(self.obj, def_name, eb[ def_bones[-1] ].tail)

                    def_bones += [ def_name ]
            else:        
                def_name = make_deformer_name( strip_org(org) )
                def_name = copy_bone( self.obj, org, def_name )
                def_bones.append( def_name )

        # Parent deform bones
        for i,b in enumerate( def_bones ):
            if i > 0: # For all bones but the first (which has no parent)
                eb[b].parent      = eb[ def_bones[i-1] ] # to previous
                eb[b].use_connect = True

        # Constraint def to tweaks
        for d,t in zip(def_bones, tweaks['ctrl']):
            tidx = tweaks['ctrl'].index(t)

            make_constraint( self, d, {
                'constraint'  : 'COPY_TRANSFORMS',
                'subtarget'   : t
            })

            if tidx != len(tweaks['ctrl']) - 1:
                make_constraint( self, d, {
                    'constraint'  : 'DAMPED_TRACK',
                    'subtarget'   : tweaks['ctrl'][ tidx + 1 ],
                })

                make_constraint( self, d, {
                    'constraint'  : 'STRETCH_TO',
                    'subtarget'   : tweaks['ctrl'][ tidx + 1 ],
                })

        # Create bbone segments
        for bone in bones['def'][:-1]:
            self.obj.data.bones[bone].bbone_segments = 8

        self.obj.data.bones[ bones['def'][0]  ].bbone_in  = 0.0
        self.obj.data.bones[ bones['def'][-2] ].bbone_out = 0.0

        # Rubber hose drivers
        pb = self.obj.pose.bones
        for i,t in enumerate( tweaks['ctrl'][1:-1] ):
            # Create custom property on tweak bone to control rubber hose
            name                = 'rubber_' + t 

            if i == trunc( len( tweaks['ctrl'][1:-1] / 2 ) ):
                pb[t][prop] = 0.0
            else:
                pb[t][prop] = 1.0

            prop                = rna_idprop_ui_prop_get( t, name, create=True )
            prop["min"]         = 0.0
            prop["max"]         = 2.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = name

            defs = def_bones[i:i+1]
            for i,d in enumerate(defs):
                drv = ''
                if i == 0:
                    drv = self.obj.bones[d].driver_add("bbone_in").driver                
                else:
                    drv = self.obj.bones[d].driver_add("bbone_out").driver                

                drv.type = 'SUM'
                var = drv.variables.new()
                var.name = name
                var.type = "SINGLE_PROP"
                var.targets[0].id = self.obj
                var.targets[0].data_path = \
                    t.path_from_id() + '[' + '"' + name + '"' + ']'

        return def_bones
        
    def create_fk( self ):
        pass
        
        retrun { 'ctrl' : ctrls, 'mch' : mch }

        
    def create_ik( self ):
        
        pass
        
        retrun { 'ctrl'       : ctrl, 
                 'mch_ik'     : mch_ik, 
                 'mch_target' : mch_target,
                 'mch_str'    : mch_str
        }
    

        

    def generate( self ):
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in self.org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None
            
        bones = {}

        # Create mch limb parent
        

        bones['tweak'] = self.create_tweak()                
        bones['def']   = self.create_def( bones['tweak']['ctrl'] )
        bones['fk']    = self.create_fk()
        bones['ik']    = self.create_ik()

        
def add_parameters( params ):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """

    params.segments = bpy.props.IntProperty(
        name        = 'bone segments',
        default     = 2,
        min         = 1,
        description = 'Number of segments'
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
        
    # Setting up extra layers for the FK and tweak
    params.fk_extra_layers = bpy.props.BoolProperty( 
        name        = "fk_extra_layers", 
        default     = True, 
        description = ""
        )

    params.fk_layers = bpy.props.BoolVectorProperty(
        size        = 32,
        description = "Layers for the FK controls to be on",
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

    for layer in [ 'tweak', 'fk' ]:
        r = layout.row()
        r.prop(params, layer + "_extra_layers")
        r.active = params.tweak_extra_layers
        
        col = r.column(align=True)
        row = col.row(align=True)

        for i in range(8):
            row.prop(params, layer + "_layers", index=i, toggle=True, text="")

        row = col.row(align=True)

        for i in range(16,24):
            row.prop(params, layer + "_layers", index=i, toggle=True, text="")

        col = r.column(align=True)
        row = col.row(align=True)

        for i in range(8,16):
            row.prop(params, layer + "_layers", index=i, toggle=True, text="")

        row = col.row(align=True)

        for i in range(24,32):
            row.prop(params, layer + "_layers", index=i, toggle=True, text="")
