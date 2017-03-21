import chromium_code_search as cs
import os
import re
import urllib
import json

override_signatures = [
    'cpp:ui::class-EventHandler::OnEvent(ui::Event *)@chromium/../../ui/events/event_handler.h|decl',
    'cpp:ui::class-EventHandler::OnKeyEvent(ui::KeyEvent *)@chromium/../../ui/events/event_handler.h|decl',
    'cpp:ui::class-EventHandler::OnMouseEvent(ui::MouseEvent *)@chromium/../../ui/events/event_handler.h|decl',
    'cpp:ui::class-EventHandler::OnScrollEvent(ui::ScrollEvent *)@chromium/../../ui/events/event_handler.h|decl',
    'cpp:ui::class-EventHandler::OnTouchEvent(ui::TouchEvent *)@chromium/../../ui/events/event_handler.h|decl',
    'cpp:ui::class-EventHandler::OnGestureEvent(ui::GestureEvent *)@chromium/../../ui/events/event_handler.h|decl',
    'cpp:ui::class-EventHandler::OnCancelMode(ui::CancelModeEvent *)@chromium/../../ui/events/event_handler.h|decl',
    'cpp:views::class-View::OnMousePressed(const ui::MouseEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnMouseDragged(const ui::MouseEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnMouseReleased(const ui::MouseEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnMouseCaptureLost()@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnMouseMoved(const ui::MouseEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnMouseEntered(const ui::MouseEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnMouseExited(const ui::MouseEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnKeyPressed(const ui::KeyEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnKeyReleased(const ui::KeyEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnMouseWheel(const ui::MouseWheelEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnDragEntered(const ui::DropTargetEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnDragUpdated(const ui::DropTargetEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnDragExited()@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnPerformDrop(const ui::DropTargetEvent &)@chromium/../../ui/views/view.h|decl',
    'cpp:views::class-View::OnDragDone()@chromium/../../ui/views/view.h|decl'
]


def WriteFile(filename, data):
  """Writes |data| to |filename|."""
  with open(filename, 'w') as f:
    f.write(data)


def GetFilePath(signature):
  """Extracts and returns the filepath from |signature|. """
  base = 'chromium/../../'
  match = re.findall(re.escape(base) + '.*\|', signature)
  return match[-1][len(base):-1]


def GetUrl(signature):
  """Returns a url to locate item defined by |signature|."""
  url = ('https://cs.chromium.org/chromium/src/{filepath}?gs={signature}&gsn={classname}')
  url = url.format(
      filepath=urllib.parse.quote(GetFilePath(signature), safe=''),
      signature=urllib.parse.quote(signature, safe=''),
      classname=urllib.parse.quote(GetClassName(signature), safe=''))
  return url


def GetClassName(signature):
  """Returns a human readable string describing the class defined by
  |signature|.
  """
  match = re.findall('^.*@', signature)
  # Remove 'cpp:' prefix, 'class-' and '@' suffix
  temp = match[-1][4:-1].replace('class-', '')
  # Remove functions
  return re.sub('::[A-Za-z0-9_]*\(.*\)', '', temp)


def GetClassSignature(function_signature):
  """Returns a class signature from a function declaration |signature|."""
  class_signature = function_signature.replace('|decl', '|def')
  return re.sub('::[A-Za-z0-9_]*\(.*\)', '', class_signature)


def GetInheritanceHierarchy(class_signature):
  """Returns a dict describing the inheritance hierarchy rooted at the class
  described by |class_signature|.

  hierarchy = {
    <class_signature_1> : {
      'extended_by' : [<subclass_signature_1>, ..., <subclass_signature_n>]
      'extends' : <parent_signature>
    }
    ...
  }
  """
  hierarchy = {}
  GetInheritanceHierarchyRec(class_signature, hierarchy)
  return hierarchy


def GetInheritanceHierarchyRec(class_signature, full_hierarchy):
  """Populates the |full_hierarchy| dict with the inheritance hierarchy rooted
  at the class described by |class_signature|.
  """
  xrefs = cs.getXrefsFor(class_signature)
  hierarchy = {}
  GetInheritanceLevel(hierarchy, xrefs)
  full_hierarchy[class_signature] = hierarchy

  if 'extended_by' not in hierarchy:
    return

  for child_signature in hierarchy['extended_by']:
    GetInheritanceHierarchyRec(child_signature, full_hierarchy)


def GetInheritanceLevel(hierarchy, xref):
  """Populates |hierarchy| with the declaration or definition found in |xref|.

  hierarchy = {
    'extends' : <parent signature>,
    'extended_by' : [<child_signature_1>, ..., <child_signature_n>]
  }
  """
  key = None
  if 'declaration' in xref:
    key = 'declaration'
  elif 'definition' in xref:
    key = 'definition'

  if not key:
    # TODO(bruthig): Log and error.
    return

  hierarchy['extends'] = xref['extends']['signature']
  hierarchy['extended_by'] = []

  if 'extended_by' not in xref:
    return

  for xref in xref['extended_by']:
    hierarchy['extended_by'].append(xref['signature'])


def GetOverrides(hierarchy, function_signature):
  """Adds an entry to each class in |hierarchy| that overrides the function
  defined by |function_signature|.

  hierarchy = {
    <class_signature_1> : {
      ...
      'overrides' : {
        <ancestor function signature> : <override function signature>
      }
      ...
    }
  }
  """
  function_xrefs = cs.getXrefsFor(function_signature)
  for function_xref in function_xrefs['overrides']:
    class_signature = GetClassSignature(function_xref['signature'])
    if class_signature in hierarchy:
      if 'overrides' not in hierarchy[class_signature]:
        hierarchy[class_signature]['overrides'] = {}
      hierarchy[class_signature]['overrides'][function_signature] = function_xref['signature']


def GetGraphviz(hierarchy):
  """Returns a Graphviz (http://www.graphviz.org/), dot language, graph string
  representing the class |hierarchy|.

  Nodes that override functions are colored green, otherwise they are colored
  red.
  """
  dot_graph = 'digraph {' + os.linesep
  nodes_str = ''
  for class_signature in hierarchy:
    class_data = hierarchy[class_signature]
    parent_node_name = GetClassName(class_signature)
    nodes_str += GetGraphvizNode(hierarchy, parent_node_name, class_signature) + os.linesep
    for child_signature in class_data['extended_by']:
      child_node_name = GetClassName(child_signature)
      dot_graph += "\"%s\" -> \"%s\"" % (parent_node_name, child_node_name) + os.linesep
  dot_graph += nodes_str + '}'
  return dot_graph


def GetGraphvizNode(hierarchy, node_name, class_signature):
  """Returns a Graphviz (http://www.graphviz.org/), dot language, node string
  representing the |node_name| class with the given |class_signature|.
  """
  color = "tomato"
  if ('overrides' in hierarchy[class_signature] and
          len(hierarchy[class_signature]['overrides'])):
      color = "palegreen"
  return ("\"%s\" [color=%s shape=rect style=\"rounded,filled\" URL=\"%s\"]" %
          (node_name, color, GetUrl(class_signature)))


def GetSpreadsheetData(hierarchy):
  """Returns a tab separated string to be imported into a spreadsheet for the
  given class |hierarchy|.
  """
  data = ''
  for class_signature in hierarchy:
    data += GetSpreadsheetRow(hierarchy, class_signature) + os.linesep
  return data


def GetSpreadsheetRow(hierarchy, class_signature):
  """Returns a tab separated string representing the row defined by
  |class_signature|.
  """
  class_data = hierarchy[class_signature]
  row_str = ""
  parent_signature = class_data['extends']
  row_str += ("%s\t%s\t%s" %
              ('=HYPERLINK("%s", "%s")' % (GetUrl(class_signature), GetClassName(class_signature)),
               class_signature,
               '=HYPERLINK("%s", "%s")' % (GetUrl(parent_signature), GetClassName(parent_signature))
               )
              )
  for override_signature in override_signatures:
    row_str += "\t"
    if ('overrides' in class_data and
            override_signature in class_data['overrides']):
      row_str += '=HYPERLINK("%s", "Y")' % GetUrl(class_data['overrides'][override_signature])
    else:
      row_str += "N"

  return row_str
