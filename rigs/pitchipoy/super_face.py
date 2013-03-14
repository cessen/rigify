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


    def create_eye_widget(rig, bone_name, size=1.0, bone_transform_name=None):
        obj = create_widget(rig, bone_name, bone_transform_name)
        if obj != None:
            verts = [(1.1920928955078125e-07*size, 0.5000000596046448*size, 0.0*size), (-0.12940943241119385*size, 0.482962965965271*size, 0.0*size), (-0.24999988079071045*size, 0.4330127537250519*size, 0.0*size), (-0.35355329513549805*size, 0.35355344414711*size, 0.0*size), (-0.43301260471343994*size, 0.2500000596046448*size, 0.0*size), (-0.4829627275466919*size, 0.12940959632396698*size, 0.0*size), (-0.49999988079071045*size, 1.0094120739267964e-07*size, 0.0*size), (-0.482962965965271*size, -0.12940940260887146*size, 0.0*size), (-0.43301260471343994*size, -0.24999986588954926*size, 0.0*size), (-0.3535534143447876*size, -0.35355323553085327*size, 0.0*size), (-0.25*size, -0.43301257491111755*size, 0.0*size), (-0.1294095516204834*size, -0.48296281695365906*size, 0.0*size), (-1.1920928955078125e-07*size, -0.4999999403953552*size, 0.0*size), (0.12940943241119385*size, -0.4829629063606262*size, 0.0*size), (0.24999988079071045*size, -0.4330127537250519*size, 0.0*size), (0.35355329513549805*size, -0.35355353355407715*size, 0.0*size), (0.4330127239227295*size, -0.25000008940696716*size, 0.0*size), (0.482962965965271*size, -0.12940965592861176*size, 0.0*size), (0.5000001192092896*size, -1.6926388468618825e-07*size, 0.0*size), (0.48296308517456055*size, 0.1294093281030655*size, 0.0*size), (0.4330129623413086*size, 0.24999980628490448*size, 0.0*size), (0.35355377197265625*size, 0.35355323553085327*size, 0.0*size), (0.25000035762786865*size, 0.43301260471343994*size, 0.0*size), (0.1294100284576416*size, 0.48296287655830383*size, 0.0*size), ]
            edges = [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4), (6, 5), (7, 6), (8, 7), (9, 8), (10, 9), (11, 10), (12, 11), (13, 12), (14, 13), (15, 14), (16, 15), (17, 16), (18, 17), (19, 18), (20, 19), (21, 20), (22, 21), (23, 22), (0, 23), ]

            mesh = obj.data
            mesh.from_pydata(verts, edges, faces)
            mesh.update()
            return obj
        else:
            return None


    def create_eyes_widget(rig, bone_name, size=1.0, bone_transform_name=None):
        obj = create_widget(rig, bone_name, bone_transform_name)
        if obj != None:
            verts = [(0.8928930759429932*size, -0.7071065902709961*size, 0.0*size), (0.8928932547569275*size, 0.7071067690849304*size, 0.0*size), (-1.8588197231292725*size, -0.9659252762794495*size, 0.0*size), (-2.100001096725464*size, -0.8660248517990112*size, 0.0*size), (-2.3071072101593018*size, -0.7071059942245483*size, 0.0*size), (-2.4660258293151855*size, -0.49999913573265076*size, 0.0*size), (-2.5659260749816895*size, -0.258818119764328*size, 0.0*size), (-2.5999999046325684*size, 8.575012770961621e-07*size, 0.0*size), (-2.5659255981445312*size, 0.2588198482990265*size, 0.0*size), (-2.4660253524780273*size, 0.5000006556510925*size, 0.0*size), (-2.3071064949035645*size, 0.7071075439453125*size, 0.0*size), (-2.099999189376831*size, 0.866025984287262*size, 0.0*size), (-1.8588184118270874*size, 0.9659261703491211*size, 0.0*size), (-1.5999996662139893*size, 1.000000238418579*size, 0.0*size), (-1.341180443763733*size, 0.9659258723258972*size, 0.0*size), (-1.0999995470046997*size, 0.8660253882408142*size, 0.0*size), (-0.8928929567337036*size, 0.7071067094802856*size, 0.0*size), (-0.892893373966217*size, -0.7071066498756409*size, 0.0*size), (-1.100000262260437*size, -0.8660252690315247*size, 0.0*size), (-1.3411810398101807*size, -0.9659255743026733*size, 0.0*size), (1.600000023841858*size, 1.0*size, 0.0*size), (1.3411810398101807*size, 0.9659258127212524*size, 0.0*size), (1.100000023841858*size, 0.8660253882408142*size, 0.0*size), (-1.600000262260437*size, -0.9999997615814209*size, 0.0*size), (1.0999997854232788*size, -0.8660252690315247*size, 0.0*size), (1.341180682182312*size, -0.9659257531166077*size, 0.0*size), (1.5999996662139893*size, -1.0*size, 0.0*size), (1.8588186502456665*size, -0.965925931930542*size, 0.0*size), (2.0999996662139893*size, -0.8660256266593933*size, 0.0*size), (2.3071064949035645*size, -0.7071071863174438*size, 0.0*size), (2.4660253524780273*size, -0.5000002980232239*size, 0.0*size), (2.5659255981445312*size, -0.25881943106651306*size, 0.0*size), (2.5999999046325684*size, -4.649122899991198e-07*size, 0.0*size), (2.5659260749816895*size, 0.25881853699684143*size, 0.0*size), (2.4660258293151855*size, 0.4999994933605194*size, 0.0*size), (2.3071072101593018*size, 0.707106351852417*size, 0.0*size), (2.1000006198883057*size, 0.8660250902175903*size, 0.0*size), (1.8588197231292725*size, 0.9659256339073181*size, 0.0*size), (-1.8070557117462158*size, -0.7727401852607727*size, 0.0*size), (-2.0000009536743164*size, -0.6928198337554932*size, 0.0*size), (-2.1656856536865234*size, -0.5656847357749939*size, 0.0*size), (-2.292820692062378*size, -0.3999992609024048*size, 0.0*size), (-2.3727407455444336*size, -0.20705445110797882*size, 0.0*size), (-2.3999998569488525*size, 7.336847716032935e-07*size, 0.0*size), (-2.3727405071258545*size, 0.207055926322937*size, 0.0*size), (-2.2928202152252197*size, 0.40000057220458984*size, 0.0*size), (-2.1656851768493652*size, 0.5656861066818237*size, 0.0*size), (-1.9999992847442627*size, 0.6928208470344543*size, 0.0*size), (-1.8070547580718994*size, 0.7727410197257996*size, 0.0*size), (-1.5999996662139893*size, 0.8000002503395081*size, 0.0*size), (-1.3929443359375*size, 0.7727407813072205*size, 0.0*size), (-1.1999995708465576*size, 0.6928203701972961*size, 0.0*size), (-1.0343143939971924*size, 0.5656854510307312*size, 0.0*size), (-1.0343146324157715*size, -0.5656852722167969*size, 0.0*size), (-1.2000001668930054*size, -0.6928201913833618*size, 0.0*size), (-1.3929448127746582*size, -0.7727404236793518*size, 0.0*size), (-1.6000001430511475*size, -0.7999997735023499*size, 0.0*size), (1.8070557117462158*size, 0.772739827632904*size, 0.0*size), (2.0000009536743164*size, 0.6928195953369141*size, 0.0*size), (2.1656856536865234*size, 0.5656843781471252*size, 0.0*size), (2.292820692062378*size, 0.39999890327453613*size, 0.0*size), (2.3727407455444336*size, 0.20705409348011017*size, 0.0*size), (2.3999998569488525*size, -1.0960745839838637e-06*size, 0.0*size), (2.3727405071258545*size, -0.20705628395080566*size, 0.0*size), (2.2928202152252197*size, -0.4000009298324585*size, 0.0*size), (2.1656851768493652*size, -0.5656863451004028*size, 0.0*size), (1.9999992847442627*size, -0.692821204662323*size, 0.0*size), (1.8070547580718994*size, -0.7727413773536682*size, 0.0*size), (1.5999996662139893*size, -0.8000004887580872*size, 0.0*size), (1.3929443359375*size, -0.7727410197257996*size, 0.0*size), (1.1999995708465576*size, -0.6928204894065857*size, 0.0*size), (1.0343143939971924*size, -0.5656855702400208*size, 0.0*size), (1.0343146324157715*size, 0.5656850337982178*size, 0.0*size), (1.2000004053115845*size, 0.6928199529647827*size, 0.0*size), (1.3929448127746582*size, 0.7727401852607727*size, 0.0*size), (1.6000001430511475*size, 0.7999995350837708*size, 0.0*size), ]
            edges = [(24, 0), (1, 22), (16, 1), (17, 0), (23, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13), (21, 20), (22, 21), (13, 14), (14, 15), (15, 16), (17, 18), (18, 19), (19, 23), (25, 24), (26, 25), (27, 26), (28, 27), (29, 28), (30, 29), (31, 30), (32, 31), (33, 32), (34, 33), (35, 34), (36, 35), (37, 36), (20, 37), (56, 38), (38, 39), (39, 40), (40, 41), (41, 42), (42, 43), (43, 44), (44, 45), (45, 46), (46, 47), (47, 48), (48, 49), (49, 50), (50, 51), (51, 52), (53, 54), (54, 55), (55, 56), (75, 57), (57, 58), (58, 59), (59, 60), (60, 61), (61, 62), (62, 63), (63, 64), (64, 65), (65, 66), (66, 67), (67, 68), (68, 69), (69, 70), (70, 71), (72, 73), (73, 74), (74, 75), (52, 72), (53, 71), ]

            mesh = obj.data
            mesh.from_pydata(verts, edges, faces)
            mesh.update()
            return obj
        else:
            return None


    def create_ctrl( self, bones ):
        org_bones = self.org_bones

        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
                
        ## eyes controls
        eye_1_e = eb[ bones['eyes'][0] ]
        eye_2_e = eb[ bones['eyes'][1] ]
        
        distance = ( eye_1_e.head - eye_2_e.head ) * 3
        
        eye_ctrl_1_name = strip_org( bones['eyes'][0] )
        eye_ctrl_2_name = strip_org( bones['eyes'][1] )
        
        eye_ctrl_1_name = copy_bone( self.obj, bones['eyes'][0], eye_ctrl_1_name )
        eye_ctrl_2_name = copy_bone( self.obj, bones['eyes'][1], eye_ctrl_2_name )
        eyes_ctrl_name  = copy_bone( self.obj, bones['eyes'][0], 'eyes'          )
        
        eye_ctrl_1_e = eb[ eye_ctrl_1_name ]
        eye_ctrl_2_e = eb[ eye_ctrl_2_name ]
        eyes_ctrl_e  = eb[ 'eyes' ]
        
        eye_ctrl_1_e.head += distance
        eye_ctrl_2_e.head += distance
        eyes_ctrl_e.head   = ( eye_ctrl_1_e.head + eye_ctrl_2_e.head ) / 2
        
        for bone in [ eye_ctrl_1_e, eye_ctrl_2_e, eyes_ctrl_e ]:
            bone.tail = bone.head + Vector( 0, 0, 0.03 )
        
        # Assign each eye widgets
        self.create_eye_widget( self.obj, eye_ctrl_1_name )
        self.create_eye_widget( self.obj, eye_ctrl_2_name )
        
        # Assign eyes widgets
        self.create_eyes_widget( self.obj, eyes_ctrl_name )
        
        ## 

    
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
            'eyes'   : [ 'eye.L',   'eye.R'   ],
            'ears'   : [ 'ear.L',   'ear.R'   ],
            'jaw'    : [ 'jaw.L',   'jaw.R'   ],
            'teeth'  : [ 'teeth.T', 'teeth.B' ],
            'tongue' : org_tongue_bones[-1]
        }
        
        self.create_tweak(org_to_tweaks)
        self.create_ctrl(org_to_ctrls)

    def create_mch( self ):

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
