import bpy, re
from   mathutils      import Vector
from   ...utils       import copy_bone, flip_bone
from   ...utils       import org, strip_org, make_deformer_name, connected_children_names, make_mechanism_name
from   ...utils       import create_circle_widget, create_sphere_widget, create_widget, create_cube_widget
from   ...utils       import MetarigError
from   rna_prop_ui    import rna_idprop_ui_prop_get
from   .super_widgets import create_face_widget, create_eye_widget, create_eyes_widget, create_ear_widget, create_jaw_widget, create_teeth_widget


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
        tongue_name = strip_org( tongue_org ) + '_master'
        
        tongue_ctrl_name = copy_bone( self.obj, tongue_org, tongue_name )
        
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
            
        bpy.ops.object.mode_set(mode ='OBJECT')    
        for bone in tweaks:
            create_face_widget( self.obj, bone )
                    
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
            for area in list( all_bones[category] ):
                for bone in all_bones[category][area]:
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

        # Parent eyelid deform bones (each lid def bone is parented to its respective MCH bone)
        def_lids = [ bone for bone in all_bones['deform']['all'] if 'lid' in bone ]
        
        for bone in def_lids:
            mch = make_mechanism_name( bone[4:] )
            eb[ bone ].parent = eb[ mch ]
        
        ## Parenting all mch bones
        
        eb[ 'MCH-eyes_parent' ].parent = None  # eyes_parent will be parented to root
        
        # parent all mch tongue bones to the jaw master control bone
        for bone in all_bones['mch']['tongue']:
            eb[ bone ].parent = eb[ all_bones['ctrls']['jaw'][0] ]

        ## Parenting the control bones
        
        # parent teeth.B and tongue master controls to the jaw master control bone
        for bone in [ 'teeth.B', 'tongue_master' ]:
            eb[ bone ].parent = eb[ all_bones['ctrls']['jaw'][0] ]

        # eyes
        eb[ 'eyes' ].parent = eb[ 'MCH-eyes_parent' ]
        
        eyes = [ bone for bone in all_bones['ctrls']['eyes'] if 'eyes' not in bone ]
        for eye in eyes:
            eb[ eye ].parent = eb[ 'eyes' ]

        ## Parenting the tweak bones

        # Jaw children (values) groups and their parents (keys)
        groups = {
            'jaw_master'         : [
                'jaw',
                'jaw.R.001',
                'jaw.L.001',
                'chin.L',
                'chin.R',
                'chin',
                'tongue.003'
                ],
            'MCH-jaw_master'     : [
                 'lip.B'
                ],
            'MCH-jaw_master.001' : [
                'lip.B.L.001',
                'lip.B.R.001'
                ],
            'MCH-jaw_master.002' : [
                'lips.L',
                'lips.R',
                'cheek.B.L.001',
                'cheek.B.R.001'
                ],
            'MCH-jaw_master.003' : [
                'lip.T',
                'lip.T.L.001',
                'lip.T.R.001'
                ],
            'MCH-jaw_master.004' : [
                'nose.002',
                'nose.004',
                'nose.L.001',
                'nose.R.001',
                'cheek.T.L.001',
                'cheek.T.R.001'
                ]
             }    
            
        for parent in list( groups.keys() ):
            for bone in groups[parent]:
                eb[ bone ].parent = eb[ parent ]
        
        # Remaining arbitrary relatioships for tweak bone parenting
        eb[ 'chin.001'   ].parent = eb[ 'chin'           ]
        eb[ 'chin.002'   ].parent = eb[ 'lip.B'          ]
        eb[ 'nose.001'   ].parent = eb[ 'nose.002'       ]
        eb[ 'nose.003'   ].parent = eb[ 'nose.002'       ]
        eb[ 'nose.005'   ].parent = eb[ 'lip.T'          ]
        eb[ 'tongue'     ].parent = eb[ 'tongue_master'  ]
        eb[ 'tongue.001' ].parent = eb[ 'MCH-tongue.001' ]
        eb[ 'tongue.002' ].parent = eb[ 'MCH-tongue.002' ]

        for bone in [ 'ear.L.002', 'ear.L.003', 'ear.L.004' ]:
            eb[ bone                       ].parent = eb[ 'ear.L' ]
            eb[ bone.replace( '.L', '.R' ) ].parent = eb[ 'ear.R' ]

        
    def make_constraits( self, constraint_type, bone, subtarget, influence = 1 ):
        org_bones = self.org_bones
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones

        owner_pb = pb[bone]
        
        if   constraint_type == 'def_tweak':

            const = owner_pb.constraints.new( 'DAMPED_TRACK' )
            const.target    = self.obj
            const.subtarget = subtarget

            const = owner_pb.constraints.new( 'STRETCH_TO' )
            const.target    = self.obj
            const.subtarget = subtarget

        elif constraint_type == 'def_lids':

            const = owner_pb.constraints.new( 'DAMPED_TRACK' )
            const.target    = self.obj
            const.subtarget = subtarget
            const.head_tail = 1.0

            const = owner_pb.constraints.new( 'STRETCH_TO' )
            const.target    = self.obj
            const.subtarget = subtarget
            const.head_tail = 1.0
        
        elif constraint_type == 'mch_eyes':
        
            const = owner_pb.constraints.new( 'DAMPED_TRACK' )
            const.target    = self.obj
            const.subtarget = subtarget
        
        elif constraint_type == 'mch_eyes_lids_follow':

            const = owner_pb.constraints.new( 'COPY_LOCATION' )
            const.target    = self.obj
            const.subtarget = subtarget
            const.head_tail = 1.0
                    
        elif constraint_type == 'mch_eyes_parent':
        
            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = subtarget
            
        elif constraint_type == 'mch_jaw_master':
        
            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = subtarget
            const.influence = influence
        
        elif constraint_type == 'tweak_copyloc':
        
            const = owner_pb.constraints.new( 'COPY_LOCATION' )
            const.target       = self.obj
            const.subtarget    = subtarget
            const.influence    = influence
            const.use_offset   = True
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'
        
        elif constraint_type == 'tweak_copy_rot_scl':
        
            const = owner_pb.constraints.new( 'COPY_ROTATION' )
            const.target       = self.obj
            const.subtarget    = subtarget
            const.use_offset   = True
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'
            
            const = owner_pb.constraints.new( 'COPY_SCALE' )
            const.target       = self.obj
            const.subtarget    = subtarget
            const.use_offset   = True
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'
        
        elif constraint_type == 'tweak_copyloc_inv':
        
            const = owner_pb.constraints.new( 'COPY_LOCATION' )
            const.target       = self.obj
            const.subtarget    = subtarget
            const.influence    = influence
            const.target_space = 'LOCAL'
            const.owner_space  = 'LOCAL'
            const.use_offset   = True
            const.invert_x     = True
            const.invert_y     = True
            const.invert_z     = True
        
        elif constraint_type == 'mch_tongue_copy_trans':
        
            const = owner_pb.constraints.new( 'COPY_TRANSFORMS' )
            const.target    = self.obj
            const.subtarget = subtarget
            const.influence = influence

    
    def constraints( self, all_bones ):
        ## Def bone constraints
      
        def_specials = {
            # 'bone'             : 'target'
            'DEF-jaw'               : 'chin',
            'DEF-chin.L'            : 'lips.L',
            'DEF-jaw.L.001'         : 'chin.L',
            'DEF-chin.R'            : 'lips.R',
            'DEF-jaw.R.001'         : 'chin.R',
            'DEF-brow.T.L.003'      : 'nose',
            'DEF-ear.L.003'         : 'ear.L.004',
            'DEF-ear.L.004'         : 'ear.L',
            'DEF-ear.R.003'         : 'ear.R.004',
            'DEF-ear.R.004'         : 'ear.R',
            'DEF-lip.B.L.001'       : 'lips.L',
            'DEF-lip.B.R.001'       : 'lips.R',
            'DEF-cheek.B.L.001'     : 'brow.T.L',
            'DEF-cheek.B.R.001'     : 'brow.T.R',
            'DEF-lip.T.L.001'       : 'lips.L',
            'DEF-lip.T.R.001'       : 'lips.R',
            'DEF-cheek.T.L.001'     : 'nose.L',
            'DEF-nose.L.001'        : 'nose.002',
            'DEF-cheek.T.R.001'     : 'nose.R',
            'DEF-nose.R.001'        : 'nose.002',
            'DEF-forehead.L'        : 'brow.T.L.003',
            'DEF-forehead.L.001'    : 'brow.T.L.002',
            'DEF-forehead.L.002'    : 'brow.T.L.001',
            'DEF-temple.L'          : 'jaw.L',
            'DEF-brow.T.R.003'      : 'nose',
            'DEF-forehead.R'        : 'brow.T.R.003',
            'DEF-forehead.R.001'    : 'brow.T.R.002',
            'DEF-forehead.R.002'    : 'brow.T.R.001',
            'DEF-temple.R'          : 'jaw.R'
        }

        pattern = r'^DEF-(\w+\.?\w?\.?\w?)(\.?)(\d*?)(\d?)$'

        for bone in [ bone for bone in all_bones['deform']['all'] if 'lid' not in bone ]:
            if bone in list( def_specials.keys() ):
                self.make_constraits('def_tweak', bone, def_specials[bone] )
            else:
                matches = re.match( pattern, bone ).groups()
                if len( matches ) > 1 and matches[-1]:
                    num = int( matches[-1] ) + 1
                    str_list = list( matches )[:-1] + [ str( num ) ]
                    tweak = "".join( str_list )
                else:
                    tweak = "".join( matches ) + ".001"
                self.make_constraits('def_tweak', bone, tweak )
        
        def_lids = sorted( [ bone for bone in all_bones['deform']['all'] if 'lid' in bone ] )
        mch_lids = sorted( [ bone for bone in all_bones['mch']['lids'] ] )
        
        def_lidsL, def_lidsR = self.symmetrical_split( def_lids )
        mch_lidsL, mch_lidsR = self.symmetrical_split( mch_lids )

        # Take the last mch_lid bone and place it at the end
        mch_lidsL = mch_lidsL[1:] + [ mch_lidsL[0] ]
        mch_lidsR = mch_lidsR[1:] + [ mch_lidsR[0] ]
        
        for boneL, boneR, mchL, mchR in zip( def_lidsL, def_lidsR, mch_lidsL, mch_lidsR ):
            self.make_constraits('def_lids', boneL, mchL )
            self.make_constraits('def_lids', boneR, mchR )

        ## MCH constraints
        
        # mch lids constraints
        for bone in all_bones['mch']['lids']:
            tweak = bone[4:]  # remove "MCH-" from bone name
            self.make_constraits('mch_eyes', bone, tweak )
        
        # mch eyes constraints
        for bone in [ 'MCH-eye.L', 'MCH-eye.R' ]:
            ctrl = bone[4:]  # remove "MCH-" from bone name
            self.make_constraits('mch_eyes', bone, ctrl )
        
        for bone in [ 'MCH-eye.L.001', 'MCH-eye.R.001' ]:
            target = bone[:-4] # remove number from the end of the name
            self.make_constraits('mch_eyes_lids_follow', bone, target )
            
        # mch eyes parent constraints
        self.make_constraits('mch_eyes_parent', 'MCH-eyes_parent', 'ORG-face' )
        
        ## Jaw constraints
        
        # jaw master mch bones
        self.make_constraits( 'mch_jaw_master', 'MCH-mouth_lock',     'jaw_master', 0.20  )
        self.make_constraits( 'mch_jaw_master', 'MCH-jaw_master',     'jaw_master', 1.00  )
        self.make_constraits( 'mch_jaw_master', 'MCH-jaw_master.001', 'jaw_master', 0.75  )
        self.make_constraits( 'mch_jaw_master', 'MCH-jaw_master.002', 'jaw_master', 0.35  )
        self.make_constraits( 'mch_jaw_master', 'MCH-jaw_master.003', 'jaw_master', 0.10  )
        self.make_constraits( 'mch_jaw_master', 'MCH-jaw_master.004', 'jaw_master', 0.025 )
        
        for bone in all_bones['mch']['jaw'][1:-1]:
            self.make_constraits( 'mch_jaw_master', bone, 'MCH-mouth_lock' )
            
        ## Tweak bones constraints
        
        # copy location constraints for tweak bones of both sides
        tweak_copyloc_L = {
            'brow.T.L.002'  : [ [ 'brow.T.L.001', 'brow.T.L.003'   ], [ 0.5, 0.5  ] ],
            'ear.L.003'     : [ [ 'ear.L.004', 'ear.L.002'         ], [ 0.5, 0.5  ] ],
            'brow.B.L.001'  : [ [ 'brow.B.L.002'                   ], [ 0.6       ] ],
            'brow.B.L.003'  : [ [ 'brow.B.L.002'                   ], [ 0.6       ] ],
            'brow.B.L.002'  : [ [ 'lid.T.L.001',                   ], [ 0.25      ] ],
            'lid.T.L.001'   : [ [ 'lid.T.L.002'                    ], [ 0.6       ] ],
            'lid.T.L.003'   : [ [ 'lid.T.L.002',                   ], [ 0.6       ] ],
            'lid.T.L.002'   : [ [ 'MCH-eye.L.001',                 ], [ 0.5       ] ],
            'lid.B.L.001'   : [ [ 'lid.B.L.002',                   ], [ 0.6       ] ],
            'lid.B.L.003'   : [ [ 'lid.B.L.002',                   ], [ 0.6       ] ],
            'lid.B.L.002'   : [ [ 'MCH-eye.L.001', 'cheek.T.L.001' ], [ 0.5, 0.1  ] ],
            'cheek.T.L.001' : [ [ 'cheek.B.L.001',                 ], [ 0.5       ] ],
            'nose.L'        : [ [ 'nose.L.001',                    ], [ 0.25      ] ],
            'nose.L.001'    : [ [ 'lip.T.L.001',                   ], [ 0.5       ] ],
            'cheek.B.L.001' : [ [ 'lips.L',                        ], [ 0.5       ] ],
            'lip.T.L.001'   : [ [ 'lips.L', 'lip.T'                ], [ 0.25, 0.5 ] ],
            'lip.B.L.001'   : [ [ 'lips.L', 'lip.B'                ], [ 0.25, 0.5 ] ]
            }
            
        for owner in list( tweak_copyloc_L.keys() ):
            
            targets, influences = tweak_copyloc_L[owner]
            for target, influence in zip( targets, influences ):

                # Left side constraints                
                self.make_constraits( 'tweak_copyloc', owner, target, influence )
                
                # create constraints for the right side too
                ownerR  = owner.replace(  '.L', '.R' )
                targetR = target.replace( '.L', '.R' )
                self.make_constraits( 'tweak_copyloc', ownerR, targetR, influence )

        # copy rotation & scale constraints for tweak bones of both sides
        tweak_copy_rot_scl_L = {
            'lip.T.L.001' : 'lip.T',
            'lip.B.L.001' : 'lip.B'
        }
        
        for owner in list( tweak_copy_rot_scl_L.keys() ):
            target    = tweak_copy_rot_scl_L[owner]
            influence = tweak_copy_rot_scl_L[owner]
            self.make_constraits( 'tweak_copy_rot_scl', owner, target )

            # create constraints for the right side too
            owner = owner.replace( '.L', '.R' )
            self.make_constraits( 'tweak_copy_rot_scl', owner, target )
            
        # inverted tweak bones constraints
        tweak_nose = {
            'nose.001' : [ 'nose.002', 0.35 ],
            'nose.003' : [ 'nose.002', 0.5  ],
            'nose.005' : [ 'lip.T',    0.5  ],
            'chin.002' : [ 'lip.B',    0.5  ]
        }
        
        for owner in list( tweak_nose.keys() ):
            target    = tweak_nose[owner][0]
            influence = tweak_nose[owner][1]
            self.make_constraits( 'tweak_copyloc_inv', owner, target, influence )
            
        # MCH tongue constraints
        divider = len( all_bones['mch']['tongue'] ) + 1
        factor  = len( all_bones['mch']['tongue'] )

        for owner in all_bones['mch']['tongue']:
            self.make_constraits( 'mch_tongue_copy_trans', owner, 'tongue_master', ( 1 / divider ) * factor )
            factor -= 1


    def drivers_and_props( self, all_bones ):
        
        bpy.ops.object.mode_set(mode ='OBJECT')
        pb = self.obj.pose.bones
        
        jaw_ctrl  = all_bones['ctrls']['jaw'][0]
        eyes_ctrl = all_bones['ctrls']['eyes'][2]

        jaw_prop  = 'mouth_lock'
        eyes_prop = 'eyes_follow'
        
        for bone, prop_name in zip( [ jaw_ctrl, eyes_ctrl ], [ jaw_prop, eyes_prop ] ):
            if bone == jaw_ctrl:
                pb[ bone ][ prop_name ] = 0.0
            else:
                pb[ bone ][ prop_name ] = 1.0

            prop = rna_idprop_ui_prop_get( pb[ bone ], prop_name )
            prop["min"]         = 0.0
            prop["max"]         = 1.0
            prop["soft_min"]    = 0.0
            prop["soft_max"]    = 1.0
            prop["description"] = prop_name
        
        # Jaw drivers
        mch_jaws = all_bones['mch']['jaw'][1:-1]
        
        for bone in mch_jaws:
            drv = pb[ bone ].constraints[1].driver_add("influence").driver
            drv.type='SUM'
            
            var = drv.variables.new()
            var.name = jaw_prop
            var.type = "SINGLE_PROP"
            var.targets[0].id = self.obj
            var.targets[0].data_path = pb[ jaw_ctrl ].path_from_id() + '['+ '"' + jaw_prop + '"' + ']'
            

        # Eyes driver
        mch_eyes_parent = all_bones['mch']['eyes_parent'][0]

        drv = pb[ mch_eyes_parent ].constraints[0].driver_add("influence").driver
        drv.type='SUM'
        
        var = drv.variables.new()
        var.name = eyes_prop
        var.type = "SINGLE_PROP"
        var.targets[0].id = self.obj
        var.targets[0].data_path = pb[ eyes_ctrl ].path_from_id() + '['+ '"' + eyes_prop + '"' + ']'
        


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
        self.constraints( all_bones )
        self.drivers_and_props( all_bones )
