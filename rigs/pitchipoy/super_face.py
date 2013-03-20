import bpy, re
from   mathutils      import Vector
from   ...utils       import copy_bone, flip_bone
from   ...utils       import org, strip_org, make_deformer_name, connected_children_names, make_mechanism_name
from   ...utils       import create_circle_widget, create_sphere_widget, create_widget, create_cube_widget
from   ...utils       import MetarigError
from   rna_prop_ui    import rna_idprop_ui_prop_get
from   .super_widgets import create_eye_widget, create_eyes_widget, create_ear_widget, create_jaw_widget, create_teeth_widget


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

        for browL, browR, foreheadL, foreheadR in zip( 
            brow_left, brow_right, forehead_left, forehead_right ):
            eb[foreheadL].tail = eb[browL].head
            eb[foreheadR].tail = eb[browR].head
        
        return { 'all' : def_bones }


    def create_ctrl( self, bones ):
        org_bones = self.org_bones

        ## create control bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # eyes ctrls
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
            bone.tail[:] = bone.head + Vector( [ 0, 0, 0.025 ] )
        
        # ears ctrls
        earL_name = strip_org( bones['ears'][0] )
        earR_name = strip_org( bones['ears'][1] )
        
        earL_ctrl_name = copy_bone( self.obj, org( bones['ears'][0] ), earL_name )
        earR_ctrl_name = copy_bone( self.obj, org( bones['ears'][1] ), earR_name )

        # jaw ctrl
        jaw_ctrl_name = strip_org( bones['jaw'][2] ) + '_master'
        jaw_ctrl_name = copy_bone( self.obj, bones['jaw'][2], jaw_ctrl_name )

        jawL_org_e = eb[ bones['jaw'][0] ]
        jawR_org_e = eb[ bones['jaw'][1] ]
        jaw_org_e  = eb[ bones['jaw'][2] ]

        eb[ jaw_ctrl_name ].head[:] = ( jawL_org_e.head + jawR_org_e.head ) / 2
        
        # teeth ctrls
        teethT_name = strip_org( bones['teeth'][0] )
        teethB_name = strip_org( bones['teeth'][1] )
        
        teethT_ctrl_name = copy_bone( self.obj, org( bones['teeth'][0] ), teethT_name )
        teethB_ctrl_name = copy_bone( self.obj, org( bones['teeth'][1] ), teethB_name )
        
        # tongue ctrl
        tongue_org  = bones['tongue'].pop()
        tongue_name = strip_org( tongue_org ) + '_ik'
        
        tongue_ctrl_name = copy_bone( self.obj, tongue_org, tongue_name )
        print( "tongue control name: ", tongue_ctrl_name )
        
        flip_bone( self.obj, tongue_ctrl_name )
        
        ## Assign widgets
        bpy.ops.object.mode_set(mode ='OBJECT')
        
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
        
        # Assign teeth widget
        create_teeth_widget( self.obj, teethT_ctrl_name )
        create_teeth_widget( self.obj, teethB_ctrl_name )
        
        # Assign tongue widget ( using the jaw widget )
        create_jaw_widget( self.obj, tongue_ctrl_name )

        return { 
            'eyes'   : [ eyeL_ctrl_name, eyeR_ctrl_name, eyes_ctrl_name ],
            'ears'   : [ earL_ctrl_name, earR_ctrl_name                 ],
            'jaw'    : [ jaw_ctrl_name                                  ],
            'teeth'  : [ teethT_ctrl_name, teethB_ctrl_name             ],
            'tongue' : [ tongue_ctrl_name                               ]
            }
            

    def create_tweak( self, bones, uniques, tails ):
        org_bones = self.org_bones

        ## create tweak bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        tweaks = []
        
        for bone in bones + list( uniques.keys() ):

            tweak_name = strip_org( bone )

            # pick name for unique bone from the uniques dictionary
            if bone in list( uniques.keys() ):
                tweak_name = uniques[bone]

            tweak_name = copy_bone( self.obj, bone, tweak_name )
            eb[ tweak_name ].use_connect = False
            eb[ tweak_name ].parent      = None

            tweaks.append( tweak_name )

            eb[ tweak_name ].tail[:] = eb[ tweak_name ].head + Vector( ( 0, 0, 0.005 ) )

            # create tail bone
            if bone in tails:
                if 'lip.T.L.001' in bone:
                    tweak_name = copy_bone( self.obj, bone,  'lips.L' )
                elif 'lip.T.R.001' in bone:
                    tweak_name = copy_bone( self.obj, bone,  'lips.R' )
                else:
                    tweak_name = copy_bone( self.obj, bone,  tweak_name )

                eb[ tweak_name ].use_connect = False
                eb[ tweak_name ].parent      = None

                eb[ tweak_name ].head    = eb[ bone ].tail
                eb[ tweak_name ].tail[:] = eb[ tweak_name ].head + Vector( ( 0, 0, 0.005 ) )
                
                tweaks.append( tweak_name )
                    
        return { 'all' : tweaks }


    def all_controls( self ):
        org_bones = self.org_bones

        org_tongue_bones  = sorted([ bone for bone in org_bones if 'tongue' in bone ])

        org_to_ctrls = {
            'eyes'   : [ 'eye.L',   'eye.R'        ],
            'ears'   : [ 'ear.L',   'ear.R'        ],
            'jaw'    : [ 'jaw.L',   'jaw.R', 'jaw' ],
            'teeth'  : [ 'teeth.T', 'teeth.B'      ],
            'tongue' : [ org_tongue_bones[0]       ]
        }

        tweak_unique = { 'lip.T.L'     : 'lip.T',
                         'lip.B.L'     : 'lip.B'  }

        org_to_ctrls = { key : [ org( bone ) for bone in org_to_ctrls[key] ] for key in org_to_ctrls.keys() }
        tweak_unique = { org( key ) : tweak_unique[key] for key in tweak_unique.keys() }

        tweak_exceptions = [] # bones not used to create tweaks
        tweak_exceptions += [ bone for bone in org_bones if 'forehead' in bone or 'temple' in bone ]
        
        tweak_tail =  [ 'brow.B.L.003', 'brow.B.R.003', 'nose.004', 'chin.001' ] 
        tweak_tail += [ 'lip.T.L.001', 'lip.T.R.001', 'tongue.002' ] 

        tweak_exceptions += [ 'lip.T.R', 'lip.B.R', 'ear.L.001', 'ear.R.001' ] + list(tweak_unique.keys())
        tweak_exceptions += [ 'face', 'cheek.T.L', 'cheek.T.R', 'cheek.B.L', 'cheek.B.R' ]
        tweak_exceptions += [ 'ear.L', 'ear.R', 'eye.L', 'eye.R' ]
        
        tweak_exceptions += org_to_ctrls.keys() 
        tweak_exceptions += org_to_ctrls['teeth']
        
        tweak_exceptions.pop( tweak_exceptions.index('tongue') )
        tweak_exceptions.pop( tweak_exceptions.index('jaw')    )
        
        tweak_exceptions = [ org( bone ) for bone in tweak_exceptions ]
        tweak_tail       = [ org( bone ) for bone in tweak_tail       ]

        org_to_tweak = sorted( [ bone for bone in org_bones if bone not in tweak_exceptions ] )

        ctrls  = self.create_ctrl( org_to_ctrls )
        tweaks = self.create_tweak( org_to_tweak, tweak_unique, tweak_tail )
        
        return { 'ctrls' : ctrls, 'tweaks' : tweaks }, tweak_unique

    def create_mch( self, jaw_ctrl, tongue_ctrl ):
        org_bones = self.org_bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        # Create eyes mch bones
        eyes = [ bone for bone in org_bones if 'eye' in bone ]

        mch_bones = { strip_org( eye ) : [] for eye in eyes }

        for eye in eyes:
            mch_name = make_mechanism_name( strip_org( eye ) )
            mch_name = copy_bone( self.obj, eye, mch_name )
            eb[ mch_name ].use_connect = False
            eb[ mch_name ].parent      = None

            mch_bones[ strip_org( eye ) ].append( mch_name )

            mch_name = copy_bone( self.obj, eye, mch_name )
            eb[ mch_name ].use_connect = False
            eb[ mch_name ].parent      = None

            mch_bones[ strip_org( eye ) ].append( mch_name )

            eb[ mch_name ].head[:] = eb[ mch_name ].tail
            eb[ mch_name ].tail[:] = eb[ mch_name ].head + Vector( ( 0, 0, 0.005 ) )
            
        # Create the eyes' parent mch
        face = [ bone for bone in org_bones if 'face' in bone ].pop()
        
        mch_name = 'eyes_parent'
        mch_name = make_mechanism_name( mch_name )
        mch_name = copy_bone( self.obj, face, mch_name )
        eb[ mch_name ].use_connect = False
        eb[ mch_name ].parent      = None
        
        eb[ mch_name ].length /= 4

        mch_bones['eyes_parent'] = [ mch_name ]
        
        # Create the lids' mch bones
        all_lids       = [ bone for bone in org_bones if 'lid' in bone ]
        lids_L, lids_R = self.symmetrical_split( all_lids )
        
        all_lids = [ lids_L, lids_R ]

        mch_bones['lids'] = []

        for i in range( 2 ):
            for bone in all_lids[i]:
                mch_name = make_mechanism_name( strip_org( bone ) )
                mch_name = copy_bone( self.obj, eyes[i], mch_name  )

                eb[ mch_name ].use_connect = False
                eb[ mch_name ].parent      = None

                eb[ mch_name ].tail[:] = eb[ bone ].head
        
                mch_bones['lids'].append( mch_name ) 
        
        mch_bones['jaw'] = []
        
        length_subtractor = eb[ jaw_ctrl ].length / 6
        # Create the jaw mch bones
        for i in range( 6 ):
            if i == 0:
                mch_name = make_mechanism_name( 'mouth_lock' )
            else:
                mch_name = make_mechanism_name( jaw_ctrl )

            mch_name = copy_bone( self.obj, jaw_ctrl, mch_name  )

            eb[ mch_name ].use_connect = False
            eb[ mch_name ].parent      = None

            eb[ mch_name ].length = eb[ jaw_ctrl ].length - length_subtractor * i

            mch_bones['jaw'].append( mch_name )

        # Tongue mch bones
        
        mch_bones['tongue'] = []
        
        # create mch bones for all tongue org_bones except the first one
        for bone in sorted([ org for org in org_bones if 'tongue' in org ])[1:]:
            mch_name = make_mechanism_name( strip_org( bone ) )
            mch_name = copy_bone( self.obj, tongue_ctrl, mch_name )

            eb[ mch_name ].use_connect = False
            eb[ mch_name ].parent      = None
            
            mch_bones['tongue'].append( mch_name )
        
        return mch_bones
        
    def parent_bones( self, all_bones, tweak_unique ):
        org_bones = self.org_bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones
        
        face_name = [ bone for bone in org_bones if 'face' in bone ].pop()
        
        # Initially parenting all bones to the face org bone.
        for category in list( all_bones.keys() ):
            print( category )
            for area in list( all_bones[category] ):
                print( "\t", area )
                for bone in all_bones[category][area]:
                    print( "\t\t", bone )
                    eb[ bone ].parent = eb[ face_name ]
        
        ## Parenting all deformation bones
        
        # Parent all the deformation bones that have respective tweaks
        def_tweaks = [ bone for bone in all_bones['deform']['all'] if bone[4:] in all_bones['tweaks']['all'] ]

        for bone in def_tweaks:
            # the def bone is parented to its corresponding tweak, 
            # whose name is the same as that of the def bone, without the "DEF-" (first 4 chars)
            eb[ bone ].parent = eb[ bone[4:] ]

        for lip_tweak in list( tweak_unique.values() ):
            # find the def bones that match unique lip_tweaks by slicing [4:-2]
            # example: 'lip.B' matches 'DEF-lip.B.R' and 'DEF-lip.B.L' if
            # you cut off the "DEF-" [4:] and the ".L" or ".R" [:-2]
            lip_defs = [ bone for bone in all_bones['deform']['all'] if bone[4:-2] == lip_tweak ]
                        
            for bone in lip_defs:
                eb[bone].parent = eb[ lip_tweak ]
  
        # parent cheek bones top respetive tweaks
        lips  = [ 'lips.L',   'lips.R'   ]
        brows = [ 'brow.T.L', 'brow.T.R' ]
        cheekB_defs = [ 'DEF-cheek.B.L', 'DEF-cheek.B.R' ]
        cheekT_defs = [ 'DEF-cheek.T.L', 'DEF-cheek.T.R' ]
        
        for lip, brow, cheekB, cheekT in zip( lips, brows, cheekB_defs, cheekT_defs ):
            eb[ cheekB ].parent = eb[ lip ]
            eb[ cheekT ].parent = eb[ brow ]
        
        # parent ear deform bones to their controls
        ear_defs  = [ 'DEF-ear.L', 'DEF-ear.L.001', 'DEF-ear.R', 'DEF-ear.R.001' ]
        ear_ctrls = [ 'ear.L', 'ear.R' ]
        
        eb[ 'DEF-jaw' ].parent = eb[ 'jaw' ] # Parent jaw def bone to jaw tweak

        for ear_ctrl in ear_ctrls:
            for ear_def in ear_defs:
                if ear_ctrl in ear_def:
                    eb[ ear_def ].parent = eb[ ear_ctrl ]
        
        ## Parenting all mch bones
        
        eb[ 'MCH-eyes_parent' ].parent = None  # eyes_parent will be parented to root
        
        # parent all mch tongue bones to the jaw master control bone
        for bone in all_bones['mch']['tongue']:
            eb[ bone ].parent = eb[ all_bones['ctrls']['jaw'][0] ]

    def create_bones(self):
        org_bones = self.org_bones
        bpy.ops.object.mode_set(mode ='EDIT')
        eb = self.obj.data.edit_bones

        # Clear parents for org bones
        for bone in org_bones:
            eb[bone].use_connect = False
            eb[bone].parent      = None

        all_bones = {}
        
        def_names           = self.create_deformation()
        ctrls, tweak_unique = self.all_controls()
        mchs                = self.create_mch( 
                                    ctrls['ctrls']['jaw'][0], 
                                    ctrls['ctrls']['tongue'][0] 
                                    )

        return { 
            'deform' : def_names, 
            'ctrls'  : ctrls['ctrls'], 
            'tweaks' : ctrls['tweaks'], 
            'mch'    : mchs 
            }, tweak_unique

    def generate(self):
        
        all_bones, tweak_unique = self.create_bones()
        self.parent_bones( all_bones, tweak_unique )
