import bpy
from mathutils import Vector
from ...utils import copy_bone
from ...utils import strip_org, make_deformer_name, connected_children_names, make_mechanism_name
from ...utils import create_circle_widget, create_sphere_widget, create_widget
from ...utils import MetarigError
from rna_prop_ui import rna_idprop_ui_prop_get

script = """
controls    = [%s]
pb          = bpy.data.objects['%s'].pose.bones
master_name = '%s'
for name in controls:
    if is_selected(name):
        layout.prop(pb[master_name], '["%s"]', text="Curvature", slider=True)
        break
"""
class Rig:
    
    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)
        self.params = params
        
        if len(self.org_bones) <= 4:
            raise MetarigError("RIGIFY ERROR: Bone '%s': listen bro, that torso rig jusaint put tugetha rite. A little hint, use at least five bones!!" % (strip_org(bone_name)))            

    def make_torso( self ):
        """ Create the torso control bone """

        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
            
        org_name  = self.org_bones[0]
        
        torso_name = self.params.torso_name
        
        ctrl_bone = eb.new(torso_name)
        ctrl_bone.head[:] = eb[org_name].head

        tail_vec = Vector((0, 0.5, 0)) * self.obj.matrix_world
        ctrl_bone.tail[:] = ctrl_bone.head + tail_vec
        
        return torso_name
        
    def make_hips( self, torso_name ):
        """ Create the hip bones """

        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        hip_org_name  = org_bones[0]
        ctrl_name     = strip_org(hip_org_name)

        # Create control bone
        ctrl_bone   = copy_bone(self.obj, hip_org, ctrl_name )
        ctrl_bone_e = eb[ctrl_name]
        
        # Flip the hips' direction to create a more natural pivot for rotation
        bpy.ops.armature.select_all(action='DESELECT')
        eb[ctrl_name].select = True
        bpy.ops.armature.switch_direction()

        # Create mechanism bone
        mch_bone   = copy_bone(self.obj, hip_org, make_mechanism_name(ctrl_name) )
        
        # Create tweak bone
        tweak_bone   = copy_bone(self.obj, ctrl_name, ctrl_name )
        tweak_bone_e = eb[tweak_bone]

        # Calculate the position of the tweak bone's tail,
        # make it continue on a straight line from the ctrl_bone
        tweak_bone_e.head[:] = ctrl_bone_e.tail
        v1    = ctrl_bone_e.head
        v2    = ctrl_bone_e.tail
        v_avg = (( v1 + v2 ) / 2) * 2.5  # 25% of the ctrl_bone's size
        
        tweak_bone_e.tail[:] = v_avg
        
        # Create mechanism driver bone
        mch_drv   = copy_bone(self.obj, tweak_bone, make_mechanism_name(ctrl_name) + "_DRV" )

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        torso_bone_e = eb[torso_name]
        ctrl_bone_e  = eb[ctrl_name]
        mch_drv_e    = eb[mch_drv]
        tweak_bone_e = eb[tweak_bone]
        mch_bone_e   = eb[mch_bone]

        # Parenting
        # torso --> hips
        ctrl_bone_e.parent  = torso_bone
        # hips  --> MCH_DRV
        mch_drv_e.parent    = ctrl_bone_e
        # MCH_DRV --> tweak_bone
        tweak_bone_e.parent = mch_drv_e
        # MCH --> tweak_bone       
        mch_bone_e.parent   = tweak_bone_e
        
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.data.pose.bones
        
        # Constraining
        # ?? the constrains of the MCH to damped track and stretch and the MCH-DRV to copy transforms with driver
        

        
    def make_spine( self, hips ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
    def make_ribs( self, spine ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
    def make_neck( self, ribs ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
    def make_head( self, neck ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
    def make_deformation(self)
    
    def make_fk(self, torso_name)
    
    def create_bones(self):

        torso       = self.make_torso( )
        hips        = self.make_hips( torso )
        spine       = self.make_spine( hips )
        ribs        = self.make_ribs( spine )
        neck        = self.make_neck( ribs )
        head        = self.make_head( neck )
        deformation = self.make_deformation( )
        fk          = self.make_fk( torso_name )

    def parent_bones(self):
    
    def constraints_and_drivers(self):
    
    def assign_widgets(self):

    def generate(self):
        
        self.create_bones()
        self.parent_bones()
        self.constraints_and_drivers()
        self.assign_widgets()



def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """
 
    params.torso_name = bpy.props.StringProperty(
        name="torso_name", 
        default="torso",
        description="The name of the torso master control bone"
        )

def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""

    r = layout.row()
    r.prop(params, "torso_name")
    
    """
    r = layout.row()
    r.label(text="Make thumb")
    r.prop(params, "thumb", text="")
    """
