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
        
        # Create the deformation and control bone chains.
        # Just copies of the original chain.
        def_chain     = []
        ctrl_chain    = []
        mch_chain     = []
        mch_drv_chain = []
        
        org_name  = self.org_bones[0]
        temp_name = strip_org(self.org_bones[0])
        
        master_name = temp_name + "_master"
        ctrl_bone_master = self.obj.data.edit_bones.new(master_name)
        ctrl_bone_master.head[:] = self.obj.data.edit_bones[org_name].head
        ctrl_bone_master.tail[:] = self.obj.data.edit_bones[self.org_bones[-1]].tail
        ctrl_bone_master.roll    = self.obj.data.edit_bones[org_name].roll
        ctrl_bone_master.parent  = self.obj.data.edit_bones[org_name].parent
        
        for i in range(len(self.org_bones)):
            eb = self.obj.data.edit_bones

            for name in eb:
                print( name.name )

            print( len( eb ))

            name = self.org_bones[i]

            # Create control and deformation bones
            temp_name    = strip_org(name)
            print( i, " base: ", temp_name )
            print( len( eb ))
            ctrl_bone    = copy_bone(self.obj, name, temp_name)
            print( i, " ctrl bone: ", ctrl_bone )
            print( len( eb ))
            mch_bone     = copy_bone(self.obj, name, make_mechanism_name(temp_name))
            print( i, " mch bone: ", mch_bone )
            print( len( eb ))
            def_bone     = copy_bone(self.obj, name, make_deformer_name(temp_name))
            print( i, " def bone: ", def_bone )
            print( len( eb ))
            mch_bone_drv = copy_bone(self.obj, name, mch_bone + "_drv")
            print( i, " drv bone: ", mch_bone_drv )
            print( len( eb ))
                        
            ctrl_bone_e     = eb[ctrl_bone]
            print( len( eb ))
            mch_bone_e      = eb[mch_bone]
            print( len( eb ))
            def_bone_e      = eb[def_bone]
            print( len( eb ))
            mch_bone_drv_e  = eb[mch_bone_drv]
            print( len( eb ))

            # Add to list
            ctrl_chain    += [ctrl_bone]
            def_chain     += [def_bone]
            mch_chain     += [mch_bone]
            mch_drv_chain += [mch_bone_drv]
            
            # Parenting
            if i == 0:
                # First ctl bone
                ctrl_bone_e.parent    = mch_bone_drv_e
                # First def bone
                def_bone_e.parent     = eb[self.org_bones[0]].parent
                # First mch driver bone
                mch_bone_drv_e.parent = eb[self.org_bones[0]].parent
            else:
                # The rest
                ctrl_bone_e.parent         = mch_bone_drv_e
                ctrl_bone_e.use_connect    = False  
                
                def_bone_e.parent          = eb[def_chain[-1]]
                def_bone_e.use_connect     = True
                
                mch_bone_drv_e.parent      = eb[ctrl_chain[-1]]
                mch_bone_drv_e.use_connect = False


                
            # Parenting mch bone
            mch_bone_e.parent = ctrl_bone_e
            mch_bone_e.use_connect = False
                
        # Creating last conrtol bone 
        ctrl_bone_last = self.obj.data.edit_bones.new(temp_name)
        ctrl_bone_last.head[:] = eb[ctrl_chain[-1]].tail
        tail_vec = Vector((0, 0.01, 0)) * self.obj.matrix_world
        ctrl_bone_last.tail[:] = eb[ctrl_chain[-1]].tail + tail_vec
        ctrl_bone_last.roll    = eb[ctrl_chain[-1]].roll
        ctrl_bone_last.parent  = eb[ctrl_chain[-1]]

        print( "After" )
        for name in eb:
            print( name )

        bpy.ops.object.mode_set(mode ='OBJECT')
        
        pb = self.obj.pose.bones
        
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
                con.subtarget = master_name
            else:
                con           = pb[deform].constraints.new('COPY_TRANSFORMS')
                con.target    = self.obj
                con.subtarget = mch
            
            # Constraining the mch bones
            if mch_chain.index(mch) == len(mch_chain) - 1:
                con           = pb[mch].constraints.new('DAMPED_TRACK')
                con.target    = self.obj
                con.subtarget = ctrl_bone_last.name
                
                con           = pb[mch].constraints.new('STRETCH_TO')
                con.target    = self.obj
                con.subtarget = ctrl_bone_last.name
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
                drv               = pb[mch_drv].driver_add("rotation", 0).driver
                drv.type          ='SCRIPTED'
                drv.expression    = '(1-sy)*pi'
                drv               = our_driver.variables.new()
                drv.name          = "scale_y"
                drv.type          = "SINGLE_PROP"
                drv.targets[0].id = self.obj
                drv.targets[0].data_path = pb[master_name].path_from_id() + '.scale.y'
            
            # Assigning shapes to control bones
            create_circle_widget(self.obj, ctrl, radius=0.3, head_tail=0.5)
