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
        
        v1    = eb[org_name].head
        v2    = eb[org_name].tail
        v_avg = (( v1 + v2 ) / 2)

        ctrl_bone = eb.new(torso_name)
        ctrl_bone.head[:] = v_avg
        
        tail_vec = Vector((0, 0.5, 0)) * self.obj.matrix_world
        ctrl_bone.tail[:] = ctrl_bone.head + tail_vec
        
        return { 'ctrl' : ctrl_bone }
        
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
        
        return { 'ctrl' : ctrl_bone, 'mch' : mch_bone, 'tweak' : tweak_bone, 'mch_drv' : mch_drv }
        
    def make_spine( self, hips ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        spine_org_bones = sorted([ bone for bone in org_bones if 'spine' in bone.lower() ], key=str.lower )
        ribs_org_bones  = sorted([ bone for bone in org_bones if 'ribs' in bone.lower() ], key=str.lower )
        
        back_org_bones = spine_org_bones + ribs_org_bones
        
        ## TODO:
        #  1. add suppor for misnumbered chain names ( bone --> bone.002 --> bone.003 )
        #     and use the parenting structure instead
        # first_spine_bone = [ bone for bone in spine_org_bones if 'hips' in bone.parent.name.lower() ].pop()        

        # Create control bones
        spine_ctrl_name = strip_org( spine_org_bones[0] )
        
        spine_ctrl_bone = eb.new( spine_ctrl_name )
        spine_ctrl_bone.head[:] = eb[spine_org_bones[0]].head
        spine_ctrl_bone.tail[:] = eb[spine_org_bones[-1]].tail
        spine_ctrl_bone.roll    = eb[spine_org_bones[0]].roll
        
        ribs_ctrl_name = strip_org( ribs_org_bones[0] )
        
        ribs_ctrl_bone = eb.new( ribs_ctrl_name )
        ribs_ctrl_bone.head[:] = eb[ribs_org_bones[0]].head
        ribs_ctrl_bone.tail[:] = eb[ribs_org_bones[-1]].tail
        ribs_ctrl_bone.roll    = eb[ribs_org_bones[0]].roll
        
        # Create mechanism stretch bone
        spine_mch_stretch_name = make_mechanism_name( strip_org( spine_org_bones[0] ) ) + 'stretch'
        
        spine_mch_stretch_bone = eb.new( spine_mch_stretch_name )
        spine_mch_stretch_bone.head[:] = eb[spine_org_bones[0]].head
        spine_mch_stretch_bone.tail[:] = eb[ribs_org_bones[-1]].tail
        spine_mch_stretch_bone.roll    = eb[spine_org_bones[0]].roll

        # Create mch_drv bone
        no_of_bones = len(back_org_bones)    
        distance_vector = ( eb[spine_mch_stretch_name].tail - eb[spine_mch_stretch_name].head ) / no_of_bones

        for i in range(no_of_bones):
            bone = eb.new(str(i))
            bone.head[:]    = eb[spine_mch_stretch_name].head + distance_vector * i
            bone.tail[:]    = bone.head + distance_vector / 4 
            bone.roll       = spine_mch_stretch_bone.roll
        
        # Create mechanism rotation bone
        ribs_mch_rotation_name = make_mechanism_name( strip_org( ribs_org_bones[0] ) ) + 'rotation'
        ribs_mch_rotation_name = copy_bone(self.obj, ribs_ctrl_bone, ribs_mch_rotation_name )

        for org in back_org_bones:
            
            # Create tweak bone
            tweak_name = strip_org(org)
            tweak_bone = copy_bone(self.obj, org, tweak_name )
            
            # Create mch bone
            mch_name = make_mechanism_name( strip_org(org) )
            mch_bone = copy_bone(self.obj, org, mch_name )
            

            


            
            
        
        
        
       
    def make_neck( self, spine ):
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

        torso_bone_e = eb[torso_name]
        ctrl_bone_e  = eb[ctrl_name]
        mch_drv_e    = eb[mch_drv]
        tweak_bone_e = eb[tweak_bone]
        mch_bone_e   = eb[mch_bone]
        
        # Parenting ???
        # torso --> hips
        ctrl_bone_e.parent  = torso_bone
        # hips  --> MCH_DRV
        mch_drv_e.parent    = ctrl_bone_e
        # MCH_DRV --> tweak_bone
        tweak_bone_e.parent = mch_drv_e
        # MCH --> tweak_bone       
        mch_bone_e.parent   = tweak_bone_e
    
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
