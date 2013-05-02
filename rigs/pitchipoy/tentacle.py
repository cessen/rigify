import bpy
from ...utils import copy_bone
from ...utils import strip_org, make_deformer_name, connected_children_names
from ...utils import create_circle_widget, create_sphere_widget
from ...utils import MetarigError

class Rig:
    
    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)
        self.params = params
        
        if params.tweak_extra_layers:
            self.tweak_layers = list( params.tweak_layers )
        else:
            self.tweak_layers = None
        
        if len(self.org_bones) <= 1:
            raise MetarigError(
                "RIGIFY ERROR: invalid rig structure" % (strip_org(bone_name))
            )


    def make_mch( self ):
        bpy.ops.object.mode_set(mode ='EDIT')

        org_bones  = self.org_bones
        mch_parent = self.object.data.bones[ org_bones[0] ].parent
        
        mch_bone = copy_bone(
            self.obj, 
            mch_parent.name,
            make_mechanism_name( strip_org( org_bones[0] ) )
        )
        
        mch_e = self.obj.data.bones[ mch_bone ] # reference edit bone
        put_bone( self.obj, mch_bone, mch_parent.head )
        
        mch_e.length /= 4 # reduce length to fourth of original
        
        return mch_bone
        

    def make_master( self ):
        bpy.ops.object.mode_set(mode ='EDIT')

        org_bones = self.org_bones
        
        master_bone = copy_bone(
            self.obj, 
            org_bones[0], 
            strip_org( org_bones[0] ) + "_master"
        )        

        # Make widgets
        bpy.ops.object.mode_set(mode ='OBJECT')        

        create_square_widget( self.obj, master_bone )

        
    def make_controls( self ):
        bpy.ops.object.mode_set(mode ='EDIT')

        org_bones = self.org_bones

        ctrl_chain = []
        for i in range( len( org_bones ) ):
            name = org_bones[i]

            ctrl_bone  = copy_bone(
                self.obj, 
                name, 
                strip_org(name)
            )

            ctrl_chain.append( ctrl_bone )

        # Make widgets
        bpy.ops.object.mode_set(mode ='OBJECT')

        for ctrl in ctrl_chain:
            create_circle_widget(self.obj, ctrl, radius=0.3, head_tail=0.5)
            
        return ctrl_chain


    def make_tweaks( self ):
        bpy.ops.object.mode_set(mode ='EDIT')

        org_bones = self.org_bones

        tweak_chain = []
        for i in range( len( org_bones ) + 1 ):
            if i == len( org_bones ):
                # Make final tweak at the tip of the tentacle
                name = org_bones[i-1]
            else:
                name = org_bones[i]

            tweak_bone = copy_bone(
                self.obj, 
                name, 
                strip_org(name) + "_tweak"
            )

            tweak_e = self.obj.data.bones[ tweak_bone ]
            
            tweak_e.length /= 2 # Set size to half
            
            if i == len( org_bones ):
                # Position final tweak at the tip
                put_bone( self.obj, tweak_bone, eb[ tweak_chain[i-1].head )
        
            tweak_chain.append( tweak_bone )

        # Make widgets
        bpy.ops.object.mode_set(mode = 'OBJECT')

        for tweak in tweak_chain:
            create_sphere_widget( self.obj, tweak )

            tweak_pb = self.obj.pose.bones[ tweak ]

            # Set locks
            if tweak_chain.index( tweak ) != len( tweak_chain ) - 1:
                tweak_pb.lock_rotation = (True, False, True)
                tweak_pb.lock_scale    = (False, True, False)
            else:
                tweak_pb.lock_rotation_w = True
                tweak_pb.lock_rotation   = (True, True, True)
                tweak_pb.lock_scale      = (True, True, True)

            # Set up tweak bone layers
            if self.tweak_layers:
                tweak_pb.bone.layers = self.tweak_layers
            
        return tweak_chain   


    def make_deform( self ):
        bpy.ops.object.mode_set(mode ='EDIT')

        org_bones = self.org_bones

        def_chain = []
        for i in range( len( org_bones ) ):
            name = org_bones[i]

            def_bone  = copy_bone(
                self.obj, 
                name, 
                make_deformer_name(strip_org(name))
            )

            def_chain.append( def_bone )
            
        return def_chain


    def parent_bones( self, all_bones ):
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.bones

        # Clear all initial parenting
        for category in all_bones:
            for bones in all_bones[category]:
                if isinstance( all_bones[category][bones], list ):
                    for bone in all_bones[category][bones]:
                        eb[bone].parent = None
                else:
                    eb[ all_bones[category][bones] ].parent = None

        # mch bone remains parentless and will be parented to root by rigify

        # Parent master bone
        eb[ all_bones['master'] ].parent = eb[ all_bones['mch'] ]

        # Parent control bones
        ctrls_n_parent = [all_bones['master']] + all_bones['control']

        for bone in ctrls_n_parent[1:]:
            previous_index    = all_bones['control'].index( bone ) - 1
            eb[ bone ].parent = eb[all_bones['control'][previous_index]]
            
        # Parent tweak bones
        tweaks = all_bones['tweak']
        for tweak in all_bones['tweak']:
            parent = ''
            if tweaks.index( tweak ) == len( tweaks ) - 1:
                parent = all_bones['control'][ -1 ]
            else:
                parent = all_bones['control'][ tweaks.index( tweak ) ]
    
            eb[ tweak ].parent = eb[ parent ]

        # Parent deform bones
        for bone in all_bones['deform'][1:]:
            previous_index = all_bones['deform'].index( bone ) - 1

            eb[ bone ].parent = eb[ all_bones['deform'][previous_index] ]
            eb[ bone ].use_connect = True

        # Parent org bones ( to tweaks by default, or to the controls )
        for org, tweak in zip( org_bones, all_bones['tweak'] ):
            eb[ org ].parent = eb[ tweak ]                
        
    
    def constraints_and_drivers( self, all_bones ):
        bpy.ops.object.mode_set(mode ='OBJECT')

        org_bones = self.org_bones
        pb        = self.obj.pose.bones
        
        ## MCH bone constraints
        mch_pb = pb[ all_bones['mch'] ]

        con           = mch_pb.constraints.new('COPY_LOCATION')
        con.target    = self.obj
        con.subtarget = pb[ org_bones[0] ].parent.name
        con.head_tail = 1.0

        con           = mch_pb.constraints.new('COPY_ROTATION')
        con.target    = self.obj
        con.subtarget = pb[ org_bones[0] ].parent.name
        
        # Setting the MCH prop
        prop = strip_org( org_bones[0] ) + "_follow"
        mch_pb[prop] = 1.0

        master_pb = pb[ all_bones['master'] ]
        
        prop = rna_idprop_ui_prop_get( master_pb, prop )
        prop["min"] = 0.0
        prop["max"] = 1.0
        prop["soft_min"] = 0.0
        prop["soft_max"] = 1.0
        prop["description"] = prop
        
        # driving the MCH follow rotation switch

        drv = mch_pb.constraints[ 1 ].driver_add("influence").driver
        drv.type='SUM'
        
        var = drv.variables.new()
        var.name = prop
        var.type = "SINGLE_PROP"
        var.targets[0].id = self.obj
        var.targets[0].data_path = \
            master_pb.path_from_id() + '['+ '"' + prop + '"' + ']'

        ## Deform bones' constraints
        for deform, tweak in zip( all_bones['deform'], all_bones['tweak'] ):
            tweaks = all_bones['tweak']
 
            con           = pb[deform].constraints.new('COPY_TRANSFORMS')
            con.target    = self.obj
            con.subtarget = tweak
           
            con           = pb[deform].constraints.new('DAMPED_TRACK')
            con.target    = self.obj
            con.subtarget = tweaks[ tweaks.index( tweak ) + 1 ]
            
            con           = pb[deform].constraints.new('STRETCH_TO')
            con.target    = self.obj
            con.subtarget = tweaks[ tweaks.index( tweak ) + 1 ]
            
        ## Control bones' constraints
            if self.params.make_rotations:
                if ctrl != ctrl_chain[0]:
                    con = pb[ctrl].constraints.new('COPY_ROTATION')
                    con.target       = self.obj
                    con.subtarget    = ctrl_chain[ctrl_chain.index(ctrl)-1]
                    con.use_offset   = True
                    con.target_space = 'LOCAL'
                    con.owner_space  = 'LOCAL'
            

    def generate(self):
        bpy.ops.object.mode_set(mode ='EDIT')
        
        # Create the deformation and control bone chains.
        # Just copies of the original chain.
        mch         = self.make_mch()
        master      = self.make_master()
        ctrl_chain  = self.make_controls()
        tweak_chain = self.make_tweaks()
        def_chain   = self.make_deform()

        all_bones = {
            'mch'    : mch,
            'master' : master,
            'ctrl'   : ctrl_chain,
            'tweak'  : tweak_chain,
            'deform' : def_chain
        }
            
        self.parent_bones( all_bones )
        self.make_constraints( all_bones )


def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """
    params.make_rotations = bpy.props.BoolProperty(
        name        = "Rotations", 
        default     = True, 
        description = "Make bones follow parent rotation"
    )

    # Setting up extra tweak layers
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
    """ Create the ui for the rig parameters.
    """

    r = layout.row()
    r.prop(params, "make_rotations")

    r = layout.row()
    r.prop(params, "tweak_extra_layers")
    r.active = params.tweak_extra_layers
    
    col = r.column(align=True)
    row = col.row(align=True)

    for i in range( 8 ): # Layers 0-7
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")

    row = col.row(align=True)

    for i in range( 16, 24 ): # Layers 16-23
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")    
    
    col = r.column(align=True)
    row = col.row(align=True)

    for i in range( 8, 16 ): # Layers 8-15
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")    

    row = col.row(align=True)

    for i in range( 24, 32 ): # Layers 24-31
        row.prop(params, "tweak_layers", index=i, toggle=True, text="")    


def create_square_widget(rig, bone_name, size=1.0, bone_transform_name=None):
    obj = create_widget(rig, bone_name, bone_transform_name)
    if obj != None:
        verts = [
            (  0.5 * size, -2.9802322387695312e-08 * size,  0.5 * size ), 
            ( -0.5 * size, -2.9802322387695312e-08 * size,  0.5 * size ), 
            (  0.5 * size,  2.9802322387695312e-08 * size, -0.5 * size ), 
            ( -0.5 * size,  2.9802322387695312e-08 * size, -0.5 * size ), 
        ]

        edges = [(0, 1), (2, 3), (0, 2), (3, 1) ]
        faces = []

        mesh = obj.data
        mesh.from_pydata(verts, edges, faces)
        mesh.update()
        mesh.update()
        return obj
    else:
        return None

