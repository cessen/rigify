import bpy, re
from mathutils import Vector
from ...utils import copy_bone, flip_bone
from ...utils import strip_org, make_deformer_name, connected_children_names, make_mechanism_name
from ...utils import create_circle_widget, create_sphere_widget, create_widget, create_cube_widget
from ...utils import MetarigError
from rna_prop_ui import rna_idprop_ui_prop_get

script = """
controls    = [%s]
head_name   = '%s'
neck_name   = '%s'
ribs_name   = '%s'
pb          = bpy.data.objects['%s'].pose.bones
torso_name  = '%s'
for name in controls:
    if is_selected(name):
        layout.prop(pb[torso_name], '["%s"]', slider=True)
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
            if 'face' in org:
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


    def create_bones(self):
        org_bones = self.org_bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None
        
        def_names = self.create_deformation()


    def generate(self):
        
        all_bones = self.create_bones()
