
import os
import bpy
import bpy.ops
from bpy.props import *

from . import QC_Properties


# uses data from io_scene_valvesource
def qc_from_vs(context):

    qctxt = ''
    indent_level = 0

    def qcln(s, indent=None):
        indent = indent or indent_level
        nonlocal qctxt
        qctxt += ('\t' * indent_level) + s + '\n'

    def qc_block_begin():
        nonlocal indent_level
        qcln('{')
        indent_level += 1

    def qc_block_end():
        nonlocal indent_level
        indent_level -= 1
        qcln('}')


    from io_scene_valvesource.utils import actionsForFilter

    bodies = []
    body_reference = None
    body_physics = None

    sequences = []

    for item in context.scene.vs.export_list:
            #layout.label(text="{item_name} {ob_type}".format(**item))
            if item.ob_type in ['COLLECTION', 'OBJECT']:
                if (not body_physics) and 'phys' in item.name.lower():
                    body_physics = item
                elif (not body_reference) and 'ref' in item.name.lower():
                    body_reference = item
                else:
                    bodies.append(item)

            elif item.ob_type == 'ACTION':
                sequences.append(item)

    qcln("// Auto-generated by Blender QC File Generator")

    props = context.scene.qcgen
    anots = QC_Properties.__annotations__
    for key in anots:
        if hasattr(props, key):
            value = getattr(props, key)
            value_type = anots[key].function
            anot = anots[key].keywords

            if 'options' in anot and 'HIDDEN' in anot['options']:
                print("IGNORED: " + key)
                continue

            # skip collections for now
            if value_type == CollectionProperty:
                continue

            # skip default values
            if 'default' in anot and value == anot['default']:
                print("SKIPPING: " + key)
                continue

            if type(value) == bool and value == True:  # bools to flags
                qcln("$%s" % key)
                continue

            if type(value) == str and value == '':  # discard empty strings
                continue

            if type(value) == str:
                if key == 'modelname':
                    # Remove models/ from $modelname
                    if value.startswith('models/') or value.startswith('models\\'):
                        value = value[7:]
                qcln('$%s "%s"' % (key, value))
            else:
                qcln('$%s %s' % (key, value))

    file_ext = '.' + (context.scene.vs.export_format.lower() or 'smd')

    from io_scene_valvesource import shouldExportGroup

    # QC Command: $command "name" "path/file.ext"
    # set name=False for nameless commands like $collisionmodel
    def qc_item(item, cmd='body', subdir='', name=None, ext=file_ext):
        
        obj = item.obj or item.collection

        should = shouldExportGroup(obj) if type(obj) == bpy.types.Collection else obj.vs.export
        if not should: return

        if subdir == '' and obj.vs.subdir and obj.vs.subdir != '.':
            subdir = obj.vs.subdir + '/'

        if name == False:
            qcln('${cmd} "{subdir}{o.name}{ext}"'.format(cmd=cmd, subdir=subdir, o=obj, ext=ext))
        else:
            name = name or obj.name
            qcln('${cmd} "{name}" "{subdir}{o.name}{ext}"'.format(cmd=cmd, subdir=subdir, o=obj, name=name, ext=ext))

    def qc_exportable(obj):
        for item in context.scene.vs.export_list:
            if item.obj and item.obj == obj:
                return item
            elif item.collection:
                if item.collection == obj:
                    return item
                else:
                    for ob in item.collection.all_objects:
                        if ob == obj:
                            return item

    if body_reference:
        qc_item(body_reference, cmd='body', name='body')

    for body in bodies:
        qc_item(body, cmd='body')

    if props.collisionmodel:
        cmd = 'collisionjoints' if props.use_collisionjoints else 'collisionmodel'
        qc_item(qc_exportable(props.collisionmodel), cmd=cmd, name=False)
        if props.concave:
            qc_block_begin()
            qcln('$concaveperjoint' if props.use_collisionjoints else '$concave')
            qc_block_end()

    if len(sequences) <= 0 and body_reference:
        qc_item(body_reference, cmd='sequence', name='idle')
    
    for seq in sequences:
        if not seq.obj:
            continue
        obj = seq.obj
        if obj.data.vs.action_selection == 'FILTERED':
            subdir = ''
            if obj.vs.subdir and obj.vs.subdir != '.':
                subdir = obj.vs.subdir + '/'
            for action in actionsForFilter(obj.vs.action_filter):
                qcln('$sequence "{o.name}" "{subdir}{o.name}{ext}"'.format(
                    subdir=subdir, o=action, ext=file_ext))
    
    return qctxt


def write_qc_file(props):
    qc_path = os.path.splitext(os.path.basename(bpy.data.filepath))[0] + ".qc"
    qc_path = os.path.join(os.path.dirname(bpy.data.filepath), qc_path)
    f = open(qc_path, 'w', encoding='utf8')

    print("Writing QC: {}".format(qc_path))
    def writef(args): print(args, file=f)

    writef("// Auto-generated by Blender QC File Generator")

    anots = QC_Properties.__annotations__
    for key in anots:
        if hasattr(props, key):
            value = getattr(props, key)
            value_type = anots[key][0]
            anot = anots[key][1]

            if 'options' in anot and 'HIDDEN' in anot['options']:
                print("IGNORED: " + key)
                continue

            # skip collections for now
            if value_type == CollectionProperty:
                continue

            # skip default values
            if 'default' in anot and value == anot['default']:
                print("SKIPPING: " + key)
                continue
            
            if type(value) == bool and value == True: # bools to flags
                writef("$%s" % key)
                continue
            
            if type(value) == str and value == '':  # discard empty strings
                continue

            if type(value) == str:
                writef('$%s "%s"' % (key, value))
            else:
                writef('$%s %s' % (key, value))

    for body in props.bodies:
        if body.component_type in {'body', 'model', 'sequence'}:
            writef('${b.component_type} "{b.name}" "{b.path}"'.format(b=body))
        elif body.component_type == 'collisionmodel':
            writef('${b.component_type} "{b.path}"'.format(b=body))
    
    f.close()

    return
