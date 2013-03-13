import bpy
from mathutils import Vector
from ...utils import copy_bone, flip_bone
from ...utils import strip_org, make_deformer_name, connected_children_names, make_mechanism_name
from ...utils import create_circle_widget, create_sphere_widget, create_widget, create_cube_widget
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
        
        if params.tweak_extra_layers:
            self.tweak_layers = list(params.tweak_layers)
        else:
            self.tweak_layers = None
        
        if params.fk_extra_layers:
            self.fk_layers = list(params.fk_layers)
        else:
            self.fk_layers = None
 
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
        
        tail_vec = Vector((0, 0.25, 0)) * self.obj.matrix_world
        ctrl_bone_e.tail[:] = ctrl_bone_e.head + tail_vec
        
        return { 'ctrl' : ctrl_bone }


    def position_bones( self, anchor, bones, size = 1 ):

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones        

        anchor_e = eb[anchor]

        no_of_bones     = len(bones)
        distance_vector = ( anchor_e.tail - anchor_e.head ) / no_of_bones
        
        for i in range(no_of_bones):
            bone_e         = eb[bones[i]]
            bone_e.head[:] = anchor_e.head + distance_vector * i
            bone_e.tail[:] = bone_e.head + distance_vector / size
            bone_e.roll    = anchor_e.roll


    def create_hips( self ):
        """ Create the hip bones """
        
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        hip_org_name   = org_bones[0]
        hip_org_bone_e = eb[hip_org_name]
        ctrl_name      = strip_org(hip_org_name)
        
        # Create ctrl
        ctrl_bone  = copy_bone(self.obj, hip_org_name, ctrl_name )
        ctrl_bone_e = eb[ctrl_bone]
        
        # Flip the hips' direction to create a more natural pivot for rotation
        flip_bone(self.obj, ctrl_name)

        # Create mch drv
        mch_drv_bone = copy_bone(self.obj, ctrl_name, make_mechanism_name(ctrl_name) + '_DRV' )
        mch_drv_bone_e = eb[mch_drv_bone]

        # Create tweak
        tweak_bone   = copy_bone(self.obj, hip_org_name, ctrl_name )
        tweak_bone_e = eb[tweak_bone]
        tweak_bone_e.tail[:] = ( tweak_bone_e.head + tweak_bone_e.tail ) / 2

        # Create mch
        mch_bone   = copy_bone(self.obj, hip_org_name, make_mechanism_name(ctrl_name) )
        
        hips_dict = {
            'ctrl'    : ctrl_bone, 
            'mch'     : mch_bone, 
            'tweak'   : tweak_bone, 
            'mch_drv' : mch_drv_bone 
        }
        
        return hips_dict
        
        
    def create_back( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        spine_org_bones = sorted([ bone for bone in org_bones if 'spine' in bone.lower() ], key=str.lower )
        ribs_org_bones  = sorted([ bone for bone in org_bones if 'ribs' in bone.lower() ], key=str.lower )
        
        back_org_bones = spine_org_bones + ribs_org_bones
        
        # Create spine ctrl bone
        spine_ctrl_name = strip_org( spine_org_bones[0] )
        
        spine_ctrl_name = copy_bone( self.obj, spine_org_bones[0], spine_ctrl_name )
        spine_ctrl_bone_e = eb[spine_ctrl_name]
        
        # Create ribs ctrl bone
        ribs_ctrl_name = strip_org( ribs_org_bones[0] )
        
        ribs_ctrl_name = copy_bone( self.obj, ribs_org_bones[0], ribs_ctrl_name )
        ribs_ctrl_bone_e = eb[ribs_ctrl_name]
        
        # Create mechanism stretch bone
        spine_mch_stretch_name = make_mechanism_name( spine_ctrl_name ) + '_stretch'
        
        spine_mch_stretch_name = copy_bone( self.obj, spine_org_bones[0], spine_mch_stretch_name )
        spine_mch_stretch_bone_e = eb[spine_mch_stretch_name]
        spine_mch_stretch_bone_e.tail[:] = eb[ribs_org_bones[-1]].tail
        
        # Positioning the back control bones along the mch stretch bone (as the anchor)
        self.position_bones( spine_mch_stretch_name, [ spine_ctrl_name, ribs_ctrl_name ] )
        
        # Create mch rotation bones
        mch_rot_bones = []
        ribs_mch_rotation_name = make_mechanism_name( ribs_ctrl_name ) + '_rotation'
        for i in range(2):
            ribs_mch_rotation_name = copy_bone(self.obj, ribs_ctrl_name, ribs_mch_rotation_name )
            mch_rot_bones.append( ribs_mch_rotation_name )
            
        no_of_bones = len(back_org_bones)
        
        # Create mch_drv bone
        mch_drv_bones = []        
        for i in range(no_of_bones):
            mch_drv_name   = make_mechanism_name( strip_org( back_org_bones[i] ) ) + '_DRV'
            mch_drv_name   = copy_bone( self.obj, spine_mch_stretch_name, mch_drv_name )
            mch_drv_bone_e = eb[mch_drv_name]
            mch_drv_bones.append( mch_drv_name )
        
        self.position_bones( spine_mch_stretch_name, mch_drv_bones, 4 )
        
        tweak_bones = []
        mch_bones   = []
        for org in back_org_bones:
            # Create tweak bones
            tweak_name = strip_org(org)
            tweak_name = copy_bone(self.obj, org, tweak_name )
            tweak_bone_e = eb[tweak_name]
            tweak_bone_e.tail = tweak_bone_e.head + ( tweak_bone_e.tail - tweak_bone_e.head ) / 2
            tweak_bone_e.parent = None 
            
            tweak_bones.append( tweak_name )
            
            # Create mch bones
            mch_name = make_mechanism_name( strip_org(org) )
            mch_bone = copy_bone(self.obj, org, mch_name )
            mch_bone_e = eb[mch_name]
             
            mch_bones.append( mch_name )
        
        back_dict = {
            'spine_ctrl'    : spine_ctrl_name,
            'ribs_ctrl'     : ribs_ctrl_name,
            'mch_stretch'   : spine_mch_stretch_name,
            'mch_rot_bones' : mch_rot_bones,
            'mch_drv_bones' : mch_drv_bones,
            'tweak_bones'   : tweak_bones,
            'mch_bones'     : mch_bones
        }
        
        return back_dict


    def create_neck( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        neck_org_bones = sorted( [ bone for bone in org_bones if 'neck' in bone.lower() ], key=str.lower )
        
        # Create ctrl bone
        ctrl_name = strip_org( neck_org_bones[0] )
        
        ctrl_name = copy_bone( self.obj,neck_org_bones[0] ,ctrl_name )
        ctrl_bone_e = eb[ctrl_name]
        ctrl_bone_e.head[:] = eb[neck_org_bones[0]].head
        ctrl_bone_e.tail[:] = eb[neck_org_bones[-1]].tail
        ctrl_bone_e.roll    = eb[neck_org_bones[0]].roll

        # Create mch rotation bone
        mch_rot_bones = []
        mch_rotation_name = make_mechanism_name( ctrl_name ) + '_rotation'
        for i in range(2):
            mch_rotation_name = copy_bone(self.obj, ctrl_name, mch_rotation_name )
            mch_rot_bones.append( mch_rotation_name )
            
        # Create mch stretch bone
        mch_stretch_name = make_mechanism_name( ctrl_name ) + '_stretch'
        mch_stretch_name = copy_bone(self.obj, ctrl_name, mch_stretch_name )
        
        mch_drv_bones = []
        tweak_bones   = []
        mch_bones     = []
        for org in neck_org_bones:
            # Create mch drv bones
            mch_drv_name   = make_mechanism_name( ctrl_name ) + '_DRV'
            mch_drv_name   = copy_bone( self.obj, org, mch_drv_name )
            mch_drv_bone_e = eb[mch_drv_name]
            mch_drv_bones.append( mch_drv_name )
            
            # Create tweak bones
            tweak_name = copy_bone( self.obj, org, ctrl_name )
            tweak_bone_e = eb[tweak_name]
            tweak_bone_e.tail = tweak_bone_e.head + ( tweak_bone_e.tail - tweak_bone_e.head ) / 2
            
            tweak_bones.append( tweak_name )
            # Create mch bones
            mch_name = make_mechanism_name( ctrl_name )
            mch_name = copy_bone( self.obj, org, mch_name )
            
            mch_bones.append( mch_name )
            
        self.position_bones( mch_stretch_name, mch_drv_bones, 4 )
        
        neck_dict = {
            'ctrl'          : ctrl_name,
            'mch_stretch'   : mch_stretch_name,
            'mch_rot_bones' : mch_rot_bones,
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
        ctrl_bone_e = eb[ctrl_name]
        
        # Create mch rotation bone
        mch_rot_bones = []
        mch_rotation_name = make_mechanism_name( ctrl_name ) + '_rotation'
        for i in range(2):
            mch_rotation_name = copy_bone(self.obj, ctrl_name, mch_rotation_name )
            mch_rot_bones.append( mch_rotation_name )
        
        # Create mch drv bone
        mch_drv_name = make_mechanism_name( ctrl_name ) + '_DRV'
        mch_drv_name = copy_bone( self.obj, org_bones[-1], mch_drv_name )
        mch_drv_bone_e = eb[mch_drv_name]
        mch_drv_bone_e.tail = mch_drv_bone_e.head + ( mch_drv_bone_e.tail - mch_drv_bone_e.head) / 4
        
        head_dict = {
            'ctrl'          : ctrl_name, 
            'mch_rot_bones' : mch_rot_bones, 
            'mch_drv'       : mch_drv_name 
        }
        
        return head_dict


    def create_fk( self, anchor_back, anchor_neck):
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
                flip_bone( self.obj, fk_name )
        
        back_fk_bones = [ name for name in fk_bones if 'spine' in name or 'ribs' in name ]
        self.position_bones( anchor_back, back_fk_bones )
        
        neck_fk_bones = [ name for name in fk_bones if 'neck' in name ]
        self.position_bones( anchor_neck, neck_fk_bones )
        
        return { 'fk_bones' : fk_bones }
        
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
        
        torso       = self.create_torso()
        hips        = self.create_hips()
        back        = self.create_back()
        neck        = self.create_neck()
        head        = self.create_head()
        fk          = self.create_fk( back['mch_stretch'], neck['mch_stretch'])
        deformation = self.create_deformation()
        
        all_bones = {
            'torso' : torso,
            'hips'  : hips,
            'back'  : back,
            'neck'  : neck,
            'head'  : head,
            'fk'    : fk,
            'def'   : deformation
        }
        
        return all_bones


    def parent_bones(self, all_bones):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Clearing out previous parenting save the org bones
        for category in all_bones.keys():
            for bones in all_bones[category].keys():
                if isinstance( all_bones[category][bones], list ):
                    for bone in all_bones[category][bones]:
                        eb[bone].parent = None
                else:
                    eb[ all_bones[category][bones] ].parent = None
        
        # Parenting the torso and its children
        torso_name = all_bones['torso']['ctrl']
        torso_bone_e = eb[torso_name]
        torso_bone_e.parent = None  # Later rigify will parent to root
        
        # Parenting the hips' bones
        
        hips_ctrl_name    = all_bones['hips']['ctrl']
        hips_mch_drv_name = all_bones['hips']['mch_drv']
        hips_tweak_name   = all_bones['hips']['tweak']
        hips_mch_name     = all_bones['hips']['mch']
        
        hips_ctrl_bone_e    = eb[hips_ctrl_name]
        hips_mch_drv_bone_e = eb[hips_mch_drv_name]
        hips_tweak_bone_e   = eb[hips_tweak_name]
        hips_mch_bone_e     = eb[hips_mch_name]
        
        hips_ctrl_bone_e.parent    = torso_bone_e
        hips_mch_drv_bone_e.parent = hips_ctrl_bone_e
        hips_tweak_bone_e.parent   = hips_mch_drv_bone_e
        hips_mch_bone_e.parent     = hips_tweak_bone_e
        
        # Parenting the back bones
        
        torso_name         = all_bones['torso']['ctrl']
        spine_ctrl_name    = all_bones['back']['spine_ctrl']
        back_mch_rot_names = all_bones['back']['mch_rot_bones']
        ribs_ctrl_name     = all_bones['back']['ribs_ctrl']
        back_mch_str_name  = all_bones['back']['mch_stretch']
        back_mch_drv_names = all_bones['back']['mch_drv_bones']
        back_tweak_names   = all_bones['back']['tweak_bones']
        back_mch_names     = all_bones['back']['mch_bones']
        
        spine_ctrl_bone_e    = eb[spine_ctrl_name]
        back_mch_rot_bones_e = [ eb[name] for name in back_mch_rot_names ]
        ribs_ctrl_bone_e     = eb[ribs_ctrl_name]
        back_mch_str_bone_e  = eb[back_mch_str_name]
        back_mch_drv_bones_e = [ eb[bone] for bone in back_mch_drv_names ]
        back_tweak_bones_e   = [ eb[bone] for bone in back_tweak_names ]
        back_mch_bones_e     = [ eb[bone] for bone in back_mch_names ]
        
        back_mch_rot_bones_e[0].parent = None
        back_mch_rot_bones_e[1].parent = spine_ctrl_bone_e
        spine_ctrl_bone_e.parent       = torso_bone_e
        ribs_ctrl_bone_e.parent        = back_mch_rot_bones_e[0]
        back_mch_str_bone_e.parent     = hips_ctrl_bone_e
        
        for drv, tweak, mch in zip( back_mch_drv_bones_e, back_tweak_bones_e, back_mch_bones_e ):
            
            if back_mch_drv_bones_e.index(drv) == 0:
                drv.parent = back_mch_str_bone_e
            else:
                drv.parent = ribs_ctrl_bone_e
            
            tweak.parent = drv
            mch.parent   = tweak
        
        # Parenting the neck bones
        neck_mch_rot_names = all_bones['neck']['mch_rot_bones']
        neck_ctrl_name     = all_bones['neck']['ctrl']
        neck_mch_str_name  = all_bones['neck']['mch_stretch']
        neck_mch_drv_names = all_bones['neck']['mch_drv_bones']
        neck_tweak_names   = all_bones['neck']['tweak_bones']
        neck_mch_names     = all_bones['neck']['mch_bones']
        
        neck_mch_rot_bones_e = [ eb[name] for name in neck_mch_rot_names ]
        neck_ctrl_bone_e     = eb[neck_ctrl_name]
        neck_mch_str_bone_e  = eb[neck_mch_str_name]
        neck_mch_drv_bones_e = [ eb[bone] for bone in neck_mch_drv_names ]
        neck_tweak_bones_e   = [ eb[bone] for bone in neck_tweak_names ]
        neck_mch_bones_e     = [ eb[bone] for bone in neck_mch_names ]
        
        neck_mch_rot_bones_e[0].parent = None  # Later rigify will parent to root
        neck_mch_rot_bones_e[1].parent = ribs_ctrl_bone_e
        neck_ctrl_bone_e.parent        = neck_mch_rot_bones_e[0]
        neck_mch_str_bone_e.parent     = neck_ctrl_bone_e
        
        for drv, tweak, mch in zip( neck_mch_drv_bones_e, neck_tweak_bones_e, neck_mch_bones_e ):
            drv.parent   = neck_mch_str_bone_e
            tweak.parent = drv
            mch.parent   = tweak
        
        # Parenting the head bones
        head_mch_rot_names = all_bones['head']['mch_rot_bones']
        head_ctrl_name     = all_bones['head']['ctrl']
        head_mch_drv_name  = all_bones['head']['mch_drv']
        
        head_mch_rot_bones_e = [ eb[name] for name in head_mch_rot_names ]
        head_ctrl_bone_e    = eb[head_ctrl_name]
        head_mch_drv_bone_e = eb[head_mch_drv_name]
        
        head_mch_rot_bones_e[0].parent = None  # Later rigify will parent to root
        head_mch_rot_bones_e[1].parent = neck_ctrl_bone_e
        head_ctrl_bone_e.parent        = head_mch_rot_bones_e[0]
        head_mch_drv_bone_e.parent     = head_mch_rot_bones_e[0]
        
        # Parenting the fk bones
        fk_names = all_bones['fk']['fk_bones']
        
        fk_bones_e = [ eb[bone] for bone in fk_names ]
        
        for bone in fk_bones_e:
            # Hips fk  parented directly to the torso bone 
            if fk_bones_e.index(bone) == 0:
                bone.parent = torso_bone_e
            # While the rest use simple chain parenting
            else:
                bone.parent = fk_bones_e[ fk_bones_e.index(bone) - 1 ]
        
        # Parenting the deformation bones
        def_names = all_bones['def']['def_bones']
        
        def_bones_e = [ eb[bone] for bone in def_names ]
        
        for bone in def_bones_e:
            if def_bones_e.index(bone) == 0:
                bone.parent = None # Later rigify will parent to root
            # While the rest use simple chain parenting
            else:
                bone.parent = def_bones_e[ def_bones_e.index(bone) - 1 ]
                bone.use_connect = True
        
        ## Parenting the org bones to tweak
        parent_bones = [ hips_tweak_name ] + back_tweak_names + neck_tweak_names + [ head_mch_drv_name ]
        
        for bone, parent in zip( org_bones, parent_bones ):
            eb[bone].parent = eb[parent]
        

    def constraints_data( self, all_bones ):
        ## Big mama: the dictionary that contains all the information about the constraints
        constraint_data = {}
        
        org_bones = self.org_bones
        
        # MCH Rotation bone names (1)
        ribs_mch_rot_names = all_bones['back']['mch_rot_bones']
        neck_mch_rot_names = all_bones['neck']['mch_rot_bones']
        head_mch_rot_names = all_bones['head']['mch_rot_bones']
        
        owner_mch_rot_bones = [ ribs_mch_rot_names[0], neck_mch_rot_names[0], head_mch_rot_names[0] ]
        
        # MCH Stretch bone names (2)
        back_mch_str_name = all_bones['back']['mch_stretch']
        neck_mch_str_name = all_bones['neck']['mch_stretch']
        
        mch_str_bones = [ back_mch_str_name, neck_mch_str_name ]
        
        # MCH DRV bone names (3)
        hips_mch_drv_name  = all_bones['hips']['mch_drv']
        back_mch_drv_names = all_bones['back']['mch_drv_bones']
        neck_mch_drv_names = all_bones['neck']['mch_drv_bones']
        head_mch_drv_name  = all_bones['head']['mch_drv']
        
        mch_drv_bones = [ hips_mch_drv_name ] + back_mch_drv_names + neck_mch_drv_names + [ head_mch_drv_name ]
        
        # MCH bone names (4)
        hips_mch_name  = all_bones['hips']['mch']
        back_mch_names = all_bones['back']['mch_bones']
        neck_mch_names = all_bones['neck']['mch_bones']
        
        mch_bones = [ hips_mch_name ] + back_mch_names + neck_mch_names
        
        # Deformation bone names (5)
        def_bones = all_bones['def']['def_bones']
        
        # referencing all subtarget bones
        torso_name      = all_bones['torso']['ctrl']
        spine_ctrl_name = all_bones['back']['spine_ctrl']
        ribs_ctrl_name  = all_bones['back']['ribs_ctrl']
        neck_ctrl_name  = all_bones['neck']['ctrl']
        head_ctrl_name  = all_bones['head']['ctrl']
        
        hips_tweak_name  = all_bones['hips']['tweak']
        back_tweak_names = all_bones['back']['tweak_bones']
        neck_tweak_names = all_bones['neck']['tweak_bones']
        
        fk_bones = all_bones['fk']['fk_bones']
        
        ### Build contraint data dictionary
        
        ## MCH Rotation constraints (1)
        subtarget_ctrl_bones    = [ spine_ctrl_name, ribs_ctrl_name, neck_ctrl_name ] 
        subtarget_mch_rot_bones = [ ribs_mch_rot_names[1], neck_mch_rot_names[1], head_mch_rot_names[1] ]
        
        # Copy_Loc and Copy_Rot for all bones:
        for bone, subtarget_ctrl, subtarget_mch_rot in zip( owner_mch_rot_bones, subtarget_ctrl_bones, subtarget_mch_rot_bones ):
            constraint_data[bone] = [ { 'constraint': 'COPY_LOCATION',
                                        'subtarget' : subtarget_ctrl,
                                        'head_tail' : 1.0               },
                                      { 'constraint': 'COPY_ROTATION', 
                                        'subtarget' : subtarget_mch_rot },
                                      { 'constraint': 'COPY_SCALE',
                                        'subtarget' : torso_name        }                    
                                    ]
        
        ## MCH Stretch constraints (2)
        subtarget_bones = [ ribs_ctrl_name, head_ctrl_name ]
        
        for bone, subtarget in zip( mch_str_bones, subtarget_bones ):
            constraint_data[bone] = [ { 'constraint' : 'DAMPED_TRACK',
                                       'subtarget'  : subtarget       },
                                     { 'constraint' : 'STRETCH_TO',
                                       'subtarget'  : subtarget       } 
                                   ]
            
            if mch_str_bones.index(bone) == 0:
                constraint_data[bone][0]['head_tail'] = 1.0
                constraint_data[bone][1]['head_tail'] = 1.0
        
        ## MCH DRV constraints (3)
        
        # Initializing constraints data stack
        for bone in mch_drv_bones:
            constraint_data[bone] = [ ]
        
        # back curve (linear falloff)
        subtarget = back_mch_str_name
        factor = 1 / len(back_mch_drv_names)
        
        for bone in back_mch_drv_names[1:-1]:
            #if back_mch_drv_names.index(bone) != 0:
            head_tail = back_mch_drv_names.index(bone) * factor
            influence = 1.0 - head_tail
            constraint_data[bone].append( { 'constraint' : 'COPY_TRANSFORMS',
                                            'subtarget'  : subtarget,
                                            'head_tail'  : head_tail,
                                            'influence'  : influence          } )
        
        # extending the last back mch drv transforms
        subtarget = ribs_ctrl_name
        constraint_data[back_mch_drv_names[-1]].extend( [ { 'constraint' : 'COPY_ROTATION',
                                                            'subtarget'  : subtarget        },
                                                          { 'constraint' : 'COPY_SCALE',
                                                            'subtarget'  : subtarget        } ] )
        
        # neck following head rotation (linear falloff)
        subtarget = head_ctrl_name
        factor = 1 / len(neck_mch_drv_names)
        
        i = 1
        for bone in neck_mch_drv_names:
            if neck_mch_drv_names.index(bone) != 0:
                influence = float(i * factor)
                constraint_data[bone].append( { 'constraint' : 'COPY_ROTATION',
                                                'subtarget'  : subtarget,
                                                'influence'  : influence       } )
                i += 1

        # head mch drv following the head control
        subtarget = head_ctrl_name
        constraint_data[head_mch_drv_name].append( { 'constraint' : 'COPY_TRANSFORMS',
                                                     'subtarget'  : subtarget          } )
        
        # fk switch constraints
        for bone, subtarget in zip( mch_drv_bones, fk_bones ):
            constraint_data[bone].append( { 'constraint' : 'COPY_TRANSFORMS',
                                            'subtarget'  : subtarget          } )
            
        ## MCH constraints (4)
        
        subtarget_bones = back_tweak_names + neck_tweak_names + [ head_mch_drv_name ]
        
        for bone, subtarget in zip( mch_bones, subtarget_bones ):
            constraint_data[bone] = [ { 'constraint' : 'DAMPED_TRACK',
                                        'subtarget'  : subtarget       },
                                      { 'constraint' : 'STRETCH_TO',
                                        'subtarget'  : subtarget       } 
                                    ]
        
        ## Deformation constraints (5)
        subtarget_bones = mch_bones + [ head_mch_drv_name ]
        
        for bone, subtarget in zip( def_bones, subtarget_bones ):
            constraint_data[bone] = [ { 'constraint' : 'COPY_TRANSFORMS',
                                        'subtarget'  : subtarget          } ]
        
        return constraint_data


    def set_constraints( self, constraint_data ):
        for bone in constraint_data.keys():
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


    def drivers_and_props( self, all_bones ):
        
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        # Referencing all relevant bones
        torso_name = all_bones['torso']['ctrl']
        pb_torso = pb[torso_name]
        
        ribs_mch_rot_names = all_bones['back']['mch_rot_bones']
        neck_mch_rot_names = all_bones['neck']['mch_rot_bones']
        head_mch_rot_names = all_bones['head']['mch_rot_bones']
        
        owner_mch_rot_bones = [ ribs_mch_rot_names[0], neck_mch_rot_names[0], head_mch_rot_names[0] ]
        
        hips_mch_drv_name  = all_bones['hips']['mch_drv']
        back_mch_drv_names = all_bones['back']['mch_drv_bones']
        neck_mch_drv_names = all_bones['neck']['mch_drv_bones']
        head_mch_drv_name  = all_bones['head']['mch_drv']
        
        mch_drv_bones = [ hips_mch_drv_name ] + back_mch_drv_names + neck_mch_drv_names + [ head_mch_drv_name ]
        
        # Setting the torso's props
        props_list = [ "ribs_follow", "neck_follow", "head_follow", "IK/FK" ]
        
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
        
        # driving the follow rotation switches for ribs neck and head
        for bone, prop, in zip( owner_mch_rot_bones, props_list[:-1] ):
            drv = pb[ bone ].constraints[ 1 ].driver_add("influence").driver
            drv.type='SUM'
            
            var = drv.variables.new()
            var.name = prop
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_torso.path_from_id() + '['+ '"' + prop + '"' + ']'
        
        # driving the fk switch
        for bone in mch_drv_bones:
            drv = pb[ bone ].constraints[ -1 ].driver_add("influence").driver
            drv.type='SUM'
            
            var = drv.variables.new()
            var.name = "fk_switch"
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb_torso.path_from_id() + '["IK/FK"]'


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
        spine_ctrl_name = all_bones['back']['spine_ctrl']
        ribs_ctrl_name  = all_bones['back']['ribs_ctrl']
        neck_ctrl_name  = all_bones['neck']['ctrl']
        head_ctrl_name  = all_bones['head']['ctrl']
        
        control_names = [ hips_ctrl_name, spine_ctrl_name, ribs_ctrl_name, neck_ctrl_name, head_ctrl_name ]
        
        hips_tweak_name  = all_bones['hips']['tweak']
        back_tweak_names = all_bones['back']['tweak_bones']
        neck_tweak_names = all_bones['neck']['tweak_bones']
        
        tweak_names = [ hips_tweak_name ] + back_tweak_names + neck_tweak_names
        
        fk_names = all_bones['fk']['fk_bones']
        
        # Assigning a widget to torso bone
        create_cube_widget(self.obj, torso_name, radius=0.5, bone_transform_name=None)
        
        # Assigning widgets to control bones
        for bone in control_names:
            create_circle_widget(self.obj, bone, radius=1.25, head_tail=0.5, with_line=False, bone_transform_name=None)
        
        # Assigning widgets to tweak bones and layers
        for bone in tweak_names:
            create_sphere_widget(self.obj, bone, bone_transform_name=None)
            
            if self.tweak_layers:
                pb[bone].bone.layers = self.tweak_layers
        
        # Assigning widgets to fk bones and layers
        for bone in fk_names:
            create_circle_widget(self.obj, bone, radius=1.0, head_tail=0.5, with_line=False, bone_transform_name=None)
            
            if self.fk_layers:
                pb[bone].bone.layers = self.fk_layers


    def generate(self):
        
        all_bones = self.create_bones()
        self.parent_bones( all_bones )
        constraint_data = self.constraints_data( all_bones )
        self.set_constraints( constraint_data )
        self.drivers_and_props( all_bones )
        self.bone_properties( all_bones )
        self.assign_widgets( all_bones )


def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """
    # varifying the name of the torso bone
    params.torso_name = bpy.props.StringProperty(
        name="torso_name", 
        default="torso",
        description="The name of the torso master control bone"
        )

    #Setting up extra layers for the FK and tweak
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
    params.fk_extra_layers = bpy.props.BoolProperty(
        name        = "fk_extra_layers",
        default     = True, 
        description = ""
        )
    params.fk_layers = bpy.props.BoolVectorProperty(
        size        = 32,
        description = "Layers for the FK controls to be on",
        default     = tuple( [ i == 2 for i in range(0, 32) ] )
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
    
    r = layout.row()
    r.prop(params, "fk_extra_layers")
    r.active = params.fk_extra_layers
    
    col = r.column(align=True)
    row = col.row(align=True)
    row.prop(params, "fk_layers", index=0, toggle=True, text="")
    row.prop(params, "fk_layers", index=1, toggle=True, text="")
    row.prop(params, "fk_layers", index=2, toggle=True, text="")
    row.prop(params, "fk_layers", index=3, toggle=True, text="")
    row.prop(params, "fk_layers", index=4, toggle=True, text="")
    row.prop(params, "fk_layers", index=5, toggle=True, text="")
    row.prop(params, "fk_layers", index=6, toggle=True, text="")
    row.prop(params, "fk_layers", index=7, toggle=True, text="")
    row = col.row(align=True)
    row.prop(params, "fk_layers", index=16, toggle=True, text="")
    row.prop(params, "fk_layers", index=17, toggle=True, text="")
    row.prop(params, "fk_layers", index=18, toggle=True, text="")
    row.prop(params, "fk_layers", index=19, toggle=True, text="")
    row.prop(params, "fk_layers", index=20, toggle=True, text="")
    row.prop(params, "fk_layers", index=21, toggle=True, text="")
    row.prop(params, "fk_layers", index=22, toggle=True, text="")
    row.prop(params, "fk_layers", index=23, toggle=True, text="")
    
    col = r.column(align=True)
    row = col.row(align=True)
    row.prop(params, "fk_layers", index=8, toggle=True, text="")
    row.prop(params, "fk_layers", index=9, toggle=True, text="")
    row.prop(params, "fk_layers", index=10, toggle=True, text="")
    row.prop(params, "fk_layers", index=11, toggle=True, text="")
    row.prop(params, "fk_layers", index=12, toggle=True, text="")
    row.prop(params, "fk_layers", index=13, toggle=True, text="")
    row.prop(params, "fk_layers", index=14, toggle=True, text="")
    row.prop(params, "fk_layers", index=15, toggle=True, text="")
    row = col.row(align=True)
    row.prop(params, "fk_layers", index=24, toggle=True, text="")
    row.prop(params, "fk_layers", index=25, toggle=True, text="")
    row.prop(params, "fk_layers", index=26, toggle=True, text="")
    row.prop(params, "fk_layers", index=27, toggle=True, text="")
    row.prop(params, "fk_layers", index=28, toggle=True, text="")
    row.prop(params, "fk_layers", index=29, toggle=True, text="")
    row.prop(params, "fk_layers", index=30, toggle=True, text="")
    row.prop(params, "fk_layers", index=31, toggle=True, text="")
    
    """
    r = layout.row()
    r.label(text="Make thumb")
    r.prop(params, "thumb", text="")
    """
