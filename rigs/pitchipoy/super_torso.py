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

    def create_torso( self ):
        """ Create the torso control bone """

        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
            
        org_name  = self.org_bones[0]
        
        torso_name = self.params.torso_name
        ctrl_bone = copy_bone(self.obj, org_name, torso_name)
        ctrl_bone_e = eb[ctrl_bone]
        
        v1    = ctrl_bone_e.head
        v2    = ctrl_bone_e.tail
        v_avg = ( v1 + v2 ) / 2
        ctrl_bone_e.head[:] = v_avg
        
        tail_vec = Vector((0, 0.5, 0)) * self.obj.matrix_world
        ctrl_bone_e.tail[:] = ctrl_bone_e.head + tail_vec
        
        return { 'ctrl' : ctrl_bone }
        
        
    def create_hips( self ):
        """ Create the hip bones """

        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        hip_org_name  = org_bones[0]
        ctrl_name     = strip_org(hip_org_name)

        # Create ctrl
        ctrl_bone  = copy_bone(self.obj, hip_org_name, ctrl_name )
        ctrl_bone_e = eb[ctrl_bone]
        
        # Flip the hips' direction to create a more natural pivot for rotation
        bpy.ops.armature.select_all(action='DESELECT')
        ctrl_bone_e.select = True
        bpy.ops.armature.switch_direction()
        
        # Create mch
        mch_bone   = copy_bone(self.obj, hip_org_name, make_mechanism_name(ctrl_name) )
        
        # Create tweak
        tweak_bone = copy_bone(self.obj, hip_org_name, ctrl_bone )
        ctrl_bone_e = eb[ctrl_bone]
        print( ctrl_bone )
        # Calculate the position of the tweak bone's tail,
        # make it continue on a straight line from the ctrl_bone
        tweak_bone_e = eb[tweak_bone]
        tweak_bone_e.head[:] = ctrl_bone_e.tail
        v1    = ctrl_bone_e.tail
        v2    = ctrl_bone_e.head
        v_avg = (( v1 + v2 ) / -4)  # 25% of the ctrl_bone's size
        tweak_bone_e.tail[:] = v_avg
        
        # Create mch drv
        mch_drv    = copy_bone(self.obj, tweak_bone, make_mechanism_name(ctrl_name) + '_DRV' )

        hips_dict = {
            'ctrl'    : ctrl_bone, 
            'mch'     : mch_bone, 
            'tweak'   : tweak_bone, 
            'mch_drv' : mch_drv 
        }
        
        return hips_dict
        
    def create_back( self ):
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

        # Create spine ctrl bone
        spine_ctrl_name = strip_org( spine_org_bones[0] )
        
        spine_ctrl_bone = copy_bone( self.obj, spine_org_bones[0], spine_ctrl_name )
        spine_ctrl_bone_e = eb[spine_ctrl_bone]
        spine_ctrl_bone_e.tail[:] = eb[spine_org_bones[-1]].tail
        
        # Create ribs ctrl bone
        ribs_ctrl_name = strip_org( ribs_org_bones[0] )
        
        ribs_ctrl_bone = copy_bone( self.obj, ribs_org_bones[0], ribs_ctrl_name )
        ribs_ctrl_bone_e = eb[ribs_ctrl_bone]
        ribs_ctrl_bone_e.tail[:] = eb[ribs_org_bones[-1]].tail

        # Create mechanism rotation bone
        ribs_mch_rotation_name = make_mechanism_name( ribs_ctrl_name ) + '_rotation'
        ribs_mch_rotation_name = copy_bone(self.obj, ribs_org_bones[0], ribs_mch_rotation_name )
        ribs_mch_stretch_bone_e = eb[ribs_mch_rotation_name]
        ribs_mch_stretch_bone_e.tail[:] = eb[ribs_org_bones[-1]].tail
        
        # Create mechanism stretch bone
        spine_mch_stretch_name = make_mechanism_name( spine_ctrl_name ) + '_stretch'
        
        spine_mch_stretch_name = copy_bone( self.obj, spine_org_bones[0], spine_mch_stretch_name )
        spine_mch_stretch_bone_e = eb[spine_mch_stretch_name]
        spine_mch_stretch_bone_e.tail[:] = eb[ribs_org_bones[-1]].tail

        # Create mch_drv bone
        no_of_bones = len(back_org_bones)    
        distance_vector = ( eb[spine_mch_stretch_name].tail - eb[spine_mch_stretch_name].head ) / no_of_bones
        
        mch_drv_bones = []        
        for i in range(no_of_bones):
            mch_drv_name = make_mechanism_name( strip_org( back_org_bones[i] ) ) + '_DRV'
            mch_drv_name = copy_bone( self.obj, spine_mch_stretch_name, mch_drv_name )
            mch_drv_bone_e = eb[mch_drv_name]
            mch_drv_bone_e.head[:] = eb[spine_mch_stretch_name].head + distance_vector * i
            mch_drv_bone_e.tail[:] = mch_drv_bone_e.head + distance_vector / 4 
            mch_drv_bone_e.roll    = spine_mch_stretch_bone_e.roll
            mch_drv_bones.append( mch_drv_name )
        
        tweak_bones = []
        mch_bones   = []
        for org in back_org_bones:
            
            # Create tweak bone
            tweak_name = strip_org(org)
            tweak_name = copy_bone(self.obj, org, tweak_name )
            tweak_bone_e = eb[tweak_name]
            tweak_bone_e.tail = tweak_bone_e.head + ( tweak_bone_e.tail - tweak_bone_e.head ) / 2

            tweak_bones.append( tweak_name )
            
            # Create mch bone
            mch_name = make_mechanism_name( strip_org(org) )
            mch_bone = copy_bone(self.obj, org, mch_name )

            mch_bones.append( mch_name )

        back_dict = {
            'spine_ctrl'    : spine_ctrl_name,
            'ribs_ctrl'     : ribs_ctrl_name,
            'mch_stretch'   : spine_mch_stretch_name,
            'mch_rotation'  : ribs_mch_rotation_name,
            'mch_drv_bones' : mch_drv_bones,
            'tweak_bones'   : tweak_bones,
            'mch_bones'     : mch_bones
        }
        
        return back_dict
       
    def create_neck( self ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        neck_org_bones = sorted([ bone for bone in org_bones if 'neck' in bone.lower() ], key=str.lower )
        
        # Create ctrl bone
        ctrl_name = strip_org( neck_org_bones[0] )
        
        ctrl_name = copy_bone( self.obj,neck_org_bones[0] ,ctrl_name )
        ctrl_bone_e = eb[ctrl_name]
        ctrl_bone_e.head[:] = eb[neck_org_bones[0]].head
        ctrl_bone_e.tail[:] = eb[neck_org_bones[-1]].tail
        ctrl_bone_e.roll    = eb[neck_org_bones[0]].roll
        
        # Create mch rotation bone
        mch_rotation_name = make_mechanism_name( ctrl_name ) + '_rotation'
        mch_rotation_name = copy_bone(self.obj, ctrl_name, mch_rotation_name )
        
        # Create mch stretch bone
        mch_stretch_name = make_mechanism_name( ctrl_name ) + '_stretch'
        mch_stretch_name = copy_bone(self.obj, ctrl_name, mch_stretch_name )
        
        mch_drv_bones = []
        tweak_bones   = []
        mch_bones     = []
        for org in neck_org_bones:
            # Create mch drv bones
            mch_drv_name = make_mechanism_name( ctrl_name ) + '_DRV'
            mch_drv_name = copy_bone( self.obj, org, mch_drv_name )
            mch_drv_bone_e = eb[mch_drv_name]
            mch_drv_bone_e.tail = mch_drv_bone_e.head + ( mch_drv_bone_e.tail - mch_drv_bone_e.head) / 4

            mch_drv_bones.append(mch_drv_name)
            
            # Create tweak bones
            tweak_name = copy_bone( self.obj, org, ctrl_name )
            tweak_bone_e = eb[tweak_name]
            tweak_bone_e.tail = tweak_bone_e.head + ( tweak_bone_e.tail - tweak_bone_e.head ) / 2

            tweak_bones.append( tweak_name )
            # Create mch bones
            mch_name = make_mechanism_name( ctrl_name )
            mch_name = copy_bone( self.obj, org, mch_name )
            
            mch_bones.append( mch_name )
        
        neck_dict = {
            'ctrl'          : ctrl_name,
            'mch_stretch'   : mch_stretch_name,
            'mch_rotation'  : mch_rotation_name,
            'mch_drv_bones' : mch_drv_bones,
            'tweak_bones'   : tweak_bones,
            'mch_bones'     : mch_bones
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
        mch_rotation_name = copy_bone( self.obj, org_bones[-1], mch_rotation_name )
        
        # Create mch drv bone
        mch_drv_name = make_mechanism_name( ctrl_name ) + '_DRV'
        mch_drv_name = copy_bone( self.obj, org_bones[-1], mch_drv_name )
        mch_drv_bone_e = eb[mch_drv_name]
        mch_drv_bone_e.tail = mch_drv_bone_e.head + ( mch_drv_bone_e.tail - mch_drv_bone_e.head) / 4

        head_dict = {
            'ctrl'         : ctrl_name, 
            'mch_rotation' : mch_rotation_name, 
            'mch_drv'      : mch_drv_name 
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
    
    def create_fk( self ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        fk_bones = []
        for org in org_bones:
            fk_name = strip_org( org ) + 'FK'
            fk_name = copy_bone( self.obj, org, fk_name )

            fk_bones.append( fk_name )
            if org_bones.index(org) == 0:
                # Flip the hips' direction to create a more natural pivot for rotation
                bpy.ops.armature.select_all(action='DESELECT')
                eb[fk_name].select = True
                bpy.ops.armature.switch_direction()

        return { 'fk_bones' : fk_bones }
                  
    
    def create_bones(self):

        torso       = self.create_torso()
        hips        = self.create_hips()
        back        = self.create_back()
        neck        = self.create_neck()
        head        = self.create_head()
        deformation = self.create_deformation()
        fk          = self.create_fk()

        all_bones = {
            'torso' : torso,
            'hips'  : hips,
            'back'  : back,
            'neck'  : neck,
            'head'  : head,
            'def'   : deformation,
            'fk'    : fk
        }

        return all_bones

    def parent_bones(self, all_bones):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Parenting the torso and its children
        torso_name = all_bones['torso']['ctrl']
        torso_bone_e = eb[torso_name]
        torso_bone_e.parent = None  # Later rigify will parent to root
        
        #...

        

        # Parenting the neck bones
        neck_mch_rot_name  = all_bones['neck']['mch_rotation']
        neck_ctrl_name     = all_bones['neck']['ctrl']
        neck_mch_str_name  = all_bones['neck']['mch_stretch']
        neck_mch_drv_names = all_bones['neck']['mch_drv_bones']
        neck_tweak_names   = all_bones['neck']['tweak_bones']
        neck_mch_names     = all_bones['neck']['mch_bones']
        
        neck_mch_rot_bone_e  = eb[neck_mch_rot_name]
        neck_ctrl_bone_e     = eb[neck_ctrl_name]
        neck_mch_str_bone_e  = eb[neck_mch_str_name]
        neck_mch_drv_bones_e = [ eb[bone] for bone in neck_mch_drv_names ]
        neck_tweak_bones_e   = [ eb[bone] for bone in neck_tweak_names ]
        neck_mch_bones_e     = [ eb[bone] for bone in neck_mch_names ]
        
        neck_mch_rot_bone_e.parent = None  # Later rigify will parent to root
        neck_ctrl_bone_e.parent    = neck_mch_rot_bone_e
        neck_mch_str_bone_e.parent = neck_ctrl_bone_e
        
        for drv, tweak, mch in zip( neck_mch_drv_bones_e, neck_tweak_bones_e, neck_mch_bones_e ):
            drv.parent   = neck_mch_str_bone_e
            tweak.parent = drv
            mch.parent   = tweak
        
        # Parenting the head bones
        head_mch_rot_name = all_bones['head']['mch_rotation']
        head_ctrl_name    = all_bones['head']['ctrl']
        head_mch_drv_name = all_bones['head']['mch_drv']

        head_mch_rot_bone_e = eb[head_mch_rot_name]
        head_ctrl_bone_e    = eb[head_ctrl_name]
        head_mch_drv_bone_e = eb[head_mch_drv_name]
        
        head_mch_rot_bone_e.parent = None  # Later rigify will parent to root
        head_ctrl_bone_e.parent    = head_mch_rot_bone_e
        head_mch_drv_bone_e.parent = head_mch_rot_bone_e
        

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
        pass
    def assign_widgets(self):
        pass
    def generate(self):
        
        all_bones = self.create_bones()
        self.parent_bones( all_bones )
        #self.constraints_and_drivers()
        #self.assign_widgets()



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
