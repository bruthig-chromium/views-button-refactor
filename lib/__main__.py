import argparse
import json
import button_refactor as br
import chromium_code_search as cs
import sys


def GenerateGraph(signature):
  filename_prefix = br.GetClassName(signature)

  hierarchy = br.GetInheritanceHierarchy(signature)
  for override_signature in br.override_signatures:
    br.GetOverrides(hierarchy, override_signature)
  br.WriteFile('%s_hierarchy.json' % filename_prefix, json.dumps(hierarchy))

  graph = br.GetGraphviz(hierarchy)
  br.WriteFile('%s_graph.dot' % filename_prefix, graph)

  spreadsheet_data = br.GetSpreadsheetData(hierarchy)
  br.WriteFile('%s_data.txt' % filename_prefix, spreadsheet_data)


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Searches Chromium Code Search for X-Refs.')
  parser.add_argument('-p', '--path',
                      help='The path to this file starting with src/')
  parser.add_argument('-w', '--word',
                      help='The word to search for in the file denoted by the path argument. You must also specify -p')
  parser.add_argument('-s', '--signature',
                      help='A signature provided from a previous search. No -p or -w arguments required.')
  args = parser.parse_args()

  signature = args.signature
  results = {}

  if not signature:
    if bool(args.path) ^ bool(args.word):
      print("Both path and word must be supplied if one is supplied")
      sys.exit(2)

    signature = cs.getSignatureFor(args.path, args.word)
    results['signature'] = signature
    if not signature:
      cs.logAndExit("Could not find signature for %s" % (args.word))

  GenerateGraph(signature)

  # print(json.dumps(br.GetInheritanceHierarchy(signature)))

  # print(json.dumps(br.GetOverrides(signatures)))
  # print(json.dumps(cs.getXrefsFor(signature)))
