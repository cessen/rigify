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
        
        if len(self.org_bones) <= 1:
            raise MetarigError(
                "RIGIFY ERROR: invalid rig structure" % (strip_org(bone_name))
            )


    def make_mch( self ):
        pass
        

    def make_master( self ):
        bpy.ops.object.mode_set(mode ='EDIT')

        org_bones = self.org_bones
        
        master_bone  = copy_bone(
            self.obj, 
            org_bones[0], 
            strip_org(name) + "_master"
        )        

        # Make widgets
        bpy.ops.object.mode_set(mode ='OBJECT')        

        
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


    def generate(self):
        bpy.ops.object.mode_set(mode ='EDIT')
        
        # Create the deformation and control bone chains.
        # Just copies of the original chain.
        mch         = self.make_mch()
        master      = ''
        ctrl_chain  = []
        tweak_chain = []
        def_chain   = self.make_deform()
        
        if self.params.master:
            master = self.make_master( name )

        if self.params.controls:
            ctrl_chain = self.make_controls( name )
        
        if self.params.tweaks:
            tweak_chain = self.make_tweaks( name )

        all_bones = {
            'mch'    : mch,
            'master' : master,
            'ctrl'   : ctrl_chain,
            'tweak'  : tweak_chain,
            'deform' : def_chain
        }
            
        self.parent_bones( all_bones )
        self.make_constraints( all_bones )






            # Create control and deformation bones
            temp_name = strip_org(name)
            ctrl_bone = copy_bone(self.obj, name, temp_name)
                        
            eb = self.obj.data.edit_bones
            ctrl_bone_e = eb[ctrl_bone]

            # Parenting
            if i == 0:
                # First ctl bone
                ctrl_bone_e.parent = eb[self.org_bones[0]].parent
                # First def bone
                def_bone_e.parent  = eb[self.org_bones[0]].parent
            else:
                # The rest
                ctrl_bone_e.parent = eb[ctrl_chain[-1]]
                ctrl_bone_e.use_connect = False
                def_bone_e.parent  = eb[def_chain[-1]]
                def_bone_e.use_connect = True
            # Add to list
            def_chain  += [def_bone]
            
        bpy.ops.object.mode_set(mode ='OBJECT')
        
        pb = self.obj.pose.bones
        
        # Constraints for org and def
        for org, ctrl, deform in zip(self.org_bones, ctrl_chain, def_chain):
 
            con           = pb[org].constraints.new('COPY_TRANSFORMS')
            con.target    = self.obj
            con.subtarget = ctrl
           
            con           = pb[deform].constraints.new('COPY_TRANSFORMS')
            con.target    = self.obj
            con.subtarget = ctrl
            
            if self.params.make_stretch:
                if deform != def_chain[-1]:
                    con           = pb[deform].constraints.new('STRETCH_TO')
                    con.target    = self.obj
                    con.subtarget = ctrl_chain[ctrl_chain.index(ctrl)+1]
                    con.volume    = 'NO_VOLUME'
                    
            if self.params.make_rotations:
                if ctrl != ctrl_chain[0]:
                    con = pb[ctrl].constraints.new('COPY_ROTATION')
                    con.target       = self.obj
                    con.subtarget    = ctrl_chain[ctrl_chain.index(ctrl)-1]
                    con.use_offset   = True
                    con.target_space = 'LOCAL'
                    con.owner_space  = 'LOCAL'
            
            create_circle_widget(self.obj, ctrl, radius=0.3, head_tail=0.5)

def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """
    params.make_stretch   = bpy.props.BoolProperty(
        name        = "Stretch", 
        default     = True, 
        description = "Enable bone stretch"
    )
    
    params.make_rotations = bpy.props.BoolProperty(
        name        = "Rotations", 
        default     = True, 
        description = "Make bones follow parent rotation"
    )


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "make_stretch")
    r = layout.row()
    r.prop(params, "make_rotations")


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

