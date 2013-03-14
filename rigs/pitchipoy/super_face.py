import bpy, re
from   mathutils      import Vector
from   ...utils       import copy_bone, flip_bone
from   ...utils       import org, strip_org, make_deformer_name, connected_children_names, make_mechanism_name
from   ...utils       import create_circle_widget, create_sphere_widget, create_widget, create_cube_widget
from   ...utils       import MetarigError
from   rna_prop_ui    import rna_idprop_ui_prop_get
from   .super_widgets import create_eye_widget, create_eyes_widget, create_ear_widget, create_jaw_widget


script = """
controls    = [%s]
head_name   = '%s'
neck_name   = '%s'
ribs_name   = '%s'
pb          = bpy.data.objects['%s'].pose.bones
torso_name  = '%s'
for name in controls:
    if is_selected(name):
        layout.prop(pb[torso_nam19:20:00e], '["%s"]', slider=True)
        break
for name in controls:
    if is_selected(name):
        if name == head_name:
            layout.prop(pb[torso_name], '["%s"]', slider=True)
            break
        if name == neck_name:
            layout.prop(pb[torso_name], '["%s"]', slider=True)
            break
        if name == ribs_name:
            layout.prop(pb[torso_name], '["%s"]', slider=True)
            break
        if name == torso_name:
            layout.prop(pb[torso_name], '["%s"]', slider=True)
            layout.prop(pb[torso_name], '["%s"]', slider=True)
            layout.prop(pb[torso_name], '["%s"]', slider=True)
            break
"""
class Rig:
    
    def __init__(self, obj, bone_name, params):
        self.obj = obj

        b = self.obj.data.bones

        self.org_bones = [bone_name] + [ b.name for b in b[bone_name].children_recursive ]
        self.params = params

    def symmetrical_split( self, bones ):

        # RE pattern match right or left parts
        # match the letter "L" (or "R"), followed by an optional dot (".") 
        # and 0 or more digits at the end of the the string
        left_pattern  = 'L\.?\d*$' 
        right_pattern = 'R\.?\d*$' 

        left  = sorted( [ name for name in bones if re.search( left_pattern,  name ) ] )
        right = sorted( [ name for name in bones if re.search( right_pattern, name ) ] )        

        return left, right
        
    def create_deformation( self ):
        org_bones = self.org_bones
        
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        def_bones = []
        for org in org_bones:
            if 'face' in org or 'teeth' in org or 'eye' in org:
                continue

            def_name = make_deformer_name( strip_org( org ) )
            def_name = copy_bone( self.obj, org, def_name )
            def_bones.append( def_name )

            eb[def_name].use_connect = False
            eb[def_name].parent      = None

        brow_top_names = [ bone for bone in def_bones if 'brow.T'   in bone ]
        forehead_names = [ bone for bone in def_bones if 'forehead' in bone ]

        brow_left, brow_right         = self.symmetrical_split( brow_top_names )
        forehead_left, forehead_right = self.symmetrical_split( forehead_names )

        brow_left  = brow_left[1:]
        brow_right = brow_right[1:]
        brow_left.reverse()
        brow_right.reverse()

        print( brow_left, "\n", brow_right )

        for browL, browR, foreheadL, foreheadR in zip( 
            brow_left, brow_right, forehead_left, forehead_right ):
            eb[foreheadL].tail = eb[browL].head
            eb[foreheadR].tail = eb[browR].head
        
        return { 'def_bones' : def_bones }
        
    def create_tweak( self, bones ):
        pass

    def create_ctrl( self, bones ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
                
        ## eyes controls
        eyeL_e = eb[ bones['eyes'][0] ]
        eyeR_e = eb[ bones['eyes'][1] ]
        
        distance = ( eyeL_e.head - eyeR_e.head ) * 3
        distance = distance.cross( (0, 0, 1) )
        
        eyeL_ctrl_name = strip_org( bones['eyes'][0] )
        eyeR_ctrl_name = strip_org( bones['eyes'][1] )
        
        eyeL_ctrl_name = copy_bone( self.obj, bones['eyes'][0],  eyeL_ctrl_name )
        eyeR_ctrl_name = copy_bone( self.obj, bones['eyes'][1],  eyeR_ctrl_name )
        eyes_ctrl_name = copy_bone( self.obj, bones['eyes'][0], 'eyes'          )
        
        eyeL_ctrl_e = eb[ eyeL_ctrl_name ]
        eyeR_ctrl_e = eb[ eyeR_ctrl_name ]
        eyes_ctrl_e = eb[ 'eyes' ]
        
        eyeL_ctrl_e.head    += distance
        eyeR_ctrl_e.head    += distance
        eyes_ctrl_e.head[:] =  ( eyeL_ctrl_e.head + eyeR_ctrl_e.head ) / 2
        
        for bone in [ eyeL_ctrl_e, eyeR_ctrl_e, eyes_ctrl_e ]:
            bone.tail[:] = bone.head + Vector( [ 0, 0, 0.03 ] )
        
        ## ears controls
        earL_name = strip_org( bones['ears'][0] )
        earR_name = strip_org( bones['ears'][1] )
        
        earL_ctrl_name = copy_bone( self.obj, org( bones['ears'][0] ), earL_name )
        earR_ctrl_name = copy_bone( self.obj, org( bones['ears'][1] ), earR_name )

        ## jaw controls
        jaw_ctrl_name = strip_org( bones['jaw'][2] )
        jaw_ctrl_name = copy_bone( self.obj, bones['jaw'][2], jaw_ctrl_name )

        jawL_org_e = eb[ bones['jaw'][0] ]
        jawR_org_e = eb[ bones['jaw'][1] ]
        jaw_org_e  = eb[ bones['jaw'][2] ]

        eb[ jaw_ctrl_name ].head[:] = ( jawL_org_e.head + jawR_org_e.head ) / 2

        bpy.ops.object.mode_set(mode ='OBJECT')

        ## Assign widgets

        # Assign each eye widgets
        create_eye_widget( self.obj, eyeL_ctrl_name )
        create_eye_widget( self.obj, eyeR_ctrl_name )
        
        # Assign eyes widgets
        create_eyes_widget( self.obj, eyes_ctrl_name )

        # Assign ears widget
        create_ear_widget( self.obj, earL_ctrl_name )
        create_ear_widget( self.obj, earR_ctrl_name )

        # Assign jaw widget
        create_jaw_widget( self.obj, jaw_ctrl_name )


    def all_controls( self ):
        org_bones = self.org_bones

        tweak_exceptions = [] # bones not used to create tweaks
        tweak_exceptions += [ bone for bone in org_bones if 'forehead' in bone or 'temple' in bone ]
        for orientation in [ 'R', 'L' ]:
            for bone in  [ 'ear.', 'cheek.T.', 'cheek.B.' ]:
                tweak_exceptions.append( bone + orientation )
            
        org_to_tweaks = [ bone for bone in org_bones if bone not in tweak_exceptions ]

        org_tongue_bones  = sorted([ bone for bone in org_bones if 'tongue' in bone ])

        org_to_ctrls = {
            'eyes'   : [ org('eye.L'),   org('eye.R')             ],
            'ears'   : [ org('ear.L'),   org('ear.R')             ],
            'jaw'    : [ org('jaw.L'),   org('jaw.R'), org('jaw') ],
            'teeth'  : [ org('teeth.T'), org('teeth.B')           ],
            'tongue' : org_tongue_bones[-1]
        }
        
        self.create_tweak(org_to_tweaks)
        self.create_ctrl(org_to_ctrls)

    def create_mch( self ):
        pass
        
    def create_bones(self):
        org_bones = self.org_bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None
        
        def_names = self.create_deformation()
        ctrls     = self.all_controls()

    def generate(self):
        
        all_bones = self.create_bones()
