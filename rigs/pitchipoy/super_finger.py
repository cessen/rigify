import bpy
from mathutils import Vector
from ...utils import copy_bone
from ...utils import strip_org, make_deformer_name, connected_children_names, make_mechanism_name
from ...utils import create_circle_widget
from ...utils import MetarigError


class Rig:
    
    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)
        self.params = params
        
        if len(self.org_bones) <= 1:
            raise MetarigError("RIGIFY ERROR: Bone '%s': listen bro, that finger rig jusaint put tugetha rite. A little hint, use more than one bone!!" % (strip_org(bone_name)))            

    def generate(self):
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Bone name lists
        ctrl_chain    = []
        def_chain     = []
        mch_chain     = []
        mch_drv_chain = []
        
        # Create ctrl master bone
        org_name  = self.org_bones[0]
        temp_name = strip_org(self.org_bones[0])
        
        master_name = temp_name + "_master"
        ctrl_bone_master = self.obj.data.edit_bones.new(master_name)
        ctrl_bone_master.head[:] = eb[org_name].head
        ctrl_bone_master.tail[:] = eb[self.org_bones[-1]].tail
        ctrl_bone_master.roll    = eb[org_name].roll
        ctrl_bone_master.parent  = eb[org_name].parent
        
        # Creating the bone chains
        for i in range(len(self.org_bones)):
            
            name      = self.org_bones[i]
            ctrl_name = strip_org(name)
            
            # Create control bones
            ctrl_bone   = copy_bone(self.obj, name, ctrl_name )
            ctrl_bone_e = eb[ctrl_name]
            
            # Create deformation bones
            def_name  = make_deformer_name(ctrl_name)
            def_bone  = copy_bone(self.obj, name, def_name )

            # Create mechanism bones
            mch_name  = make_mechanism_name(ctrl_name)
            mch_bone  = copy_bone(self.obj, name, mch_name )
            
            # Create mechanism driver bones
            drv_name  = make_mechanism_name(ctrl_name) + "_drv"
            mch_bone_drv    = copy_bone(self.obj, name, drv_name)
            mch_bone_drv_e  = eb[drv_name]
            
            # Adding to lists
            ctrl_chain    += [ctrl_name]
            def_chain     += [def_bone] 
            mch_chain     += [mch_bone]
            mch_drv_chain += [drv_name]
        
        # Clear initial parenting
        for b in eb:
            if b not in self.org_bones:
                b.parent = None
        
        # Parenting chain bones
        for i in range(len(self.org_bones)):
            # Edit bone references
            def_bone_e     = eb[def_chain[i]]
            ctrl_bone_e    = eb[ctrl_chain[i]]
            mch_bone_e     = eb[mch_chain[i]]
            mch_bone_drv_e = eb[mch_drv_chain[i]]
            
            if i == 0:
                # First ctl bone
                ctrl_bone_e.parent      = mch_bone_drv_e
                ctrl_bone_e.use_connect = False
                # First def bone
                def_bone_e.parent       = eb[self.org_bones[i]].parent
                def_bone_e.use_connect  = False
                # First mch driver bone
                mch_bone_drv_e.parent = eb[self.org_bones[i]].parent
                mch_bone_drv_e.use_connect  = False
            else:
                # The rest
                print (ctrl_bone_e.parent)
                ctrl_bone_e.parent         = mch_bone_drv_e
                ctrl_bone_e.use_connect    = False 
                print (ctrl_bone_e.parent)
                
                print (def_bone_e.parent)
                def_bone_e.parent          = eb[def_chain[i-1]]
                def_bone_e.use_connect     = True
                print (def_bone_e.parent)
                
                print (mch_bone_drv_e.parent)
                mch_bone_drv_e.parent      = eb[ctrl_chain[i-1]]
                mch_bone_drv_e.use_connect = False
                print (mch_bone_drv_e.parent)

            # Parenting mch bone
            mch_bone_e.parent = ctrl_bone_e
            mch_bone_e.use_connect = False
                
        # Creating tip conrtol bone 
        ctrl_bone_tip = self.obj.data.edit_bones.new(temp_name)
        ctrl_bone_tip.head[:] = eb[ctrl_chain[-1]].tail
        tail_vec = Vector((0, 0.1, 0)) * self.obj.matrix_world
        ctrl_bone_tip.tail[:] = eb[ctrl_chain[-1]].tail + tail_vec
        ctrl_bone_tip.roll    = eb[ctrl_chain[-1]].roll
        ctrl_bone_tip.parent  = eb[ctrl_chain[-1]]
        tip_name    = ctrl_bone_tip.name

        bpy.ops.object.mode_set(mode ='OBJECT')
        
        pb = self.obj.pose.bones
        
        # Setting pose bones locks
        pb[master_name].lock_scale = True,False,True
        
        pb[tip_name].lock_scale    = True,True,True
        pb[tip_name].lock_rotation = True,True,True
        
        # Pose settings
        for org, ctrl, deform, mch, mch_drv in zip(self.org_bones, ctrl_chain, def_chain, mch_chain, mch_drv_chain):
            
            # Constraining the org bones
            con           = pb[org].constraints.new('COPY_TRANSFORMS')
            con.target    = self.obj
            con.subtarget = ctrl

            # Constraining the deform bones
            if def_chain.index(deform) == 0:
                con           = pb[deform].constraints.new('COPY_LOCATION')
                con.target    = self.obj
                con.subtarget = master_name
                
                con           = pb[deform].constraints.new('DAMPED_TRACK')
                con.target    = self.obj
                con.subtarget = ctrl_chain[ctrl_chain.index(ctrl)+1]
            else:
                con           = pb[deform].constraints.new('COPY_TRANSFORMS')
                con.target    = self.obj
                con.subtarget = mch
            
            # Constraining the mch bones
            if mch_chain.index(mch) == len(mch_chain) - 1:
                con           = pb[mch].constraints.new('DAMPED_TRACK')
                con.target    = self.obj
                con.subtarget = tip_name
                
                con           = pb[mch].constraints.new('STRETCH_TO')
                con.target    = self.obj
                con.subtarget = tip_name
                con.volume    = 'NO_VOLUME'
            else:
                con           = pb[mch].constraints.new('DAMPED_TRACK')
                con.target    = self.obj
                con.subtarget = ctrl_chain[ctrl_chain.index(ctrl)+1]
                
                con           = pb[mch].constraints.new('STRETCH_TO')
                con.target    = self.obj
                con.subtarget = ctrl_chain[ctrl_chain.index(ctrl)+1]
                con.volume    = 'NO_VOLUME'

            # Constraining and driving mch driver bones
            pb[mch_drv].rotation_mode = 'YZX'
            
            if mch_drv_chain.index(mch_drv) == 0:
                # Constraining to master bone
                con           = pb[mch_drv].constraints.new('COPY_LOCATION')
                con.target    = self.obj
                con.subtarget = master_name
                
                con           = pb[mch_drv].constraints.new('COPY_ROTATION')
                con.target    = self.obj
                con.subtarget = master_name
            
            else:
                # Drivers
                drv                          = pb[mch_drv].driver_add("rotation_euler", 0).driver
                drv.type                     = 'SCRIPTED'
                drv.expression               = '(1-sy)*pi'
                drv_var                      = drv.variables.new()
                drv_var.name                 = 'sy'
                drv_var.type                 = "SINGLE_PROP"
                drv_var.targets[0].id        = self.obj
                drv_var.targets[0].data_path = pb[master_name].path_from_id() + '.scale.y'
            
            # Assigning shapes to control bones
            create_circle_widget(self.obj, ctrl, radius=0.3, head_tail=0.5)
