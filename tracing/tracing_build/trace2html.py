# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import codecs
import base64
import gzip
import json
import os
import StringIO
import sys

import tracing_project

from tvcm import generate


def Main(argv):

  parser = argparse.ArgumentParser(
      usage='%(prog)s <options> trace_file1 [trace_file2 ...]',
      epilog='Takes the provided trace file and produces a standalone HTML\n'
             'file that contains both the trace and the trace viewer.')

  project = tracing_project.TracingProject()
  project.AddConfigNameOptionToParser(parser)

  parser.add_argument(
      '--output', dest='output',
      help='Where to put the generated result. If not '
           'given, the trace filename is used, with an html suffix.')
  parser.add_argument(
      '--quiet', action='store_true',
      help='Dont print the output file name')
  parser.add_argument('trace_files', nargs='+')
  args = parser.parse_args(argv[1:])

  if args.output:
    output_filename = args.output
  elif len(args.trace_files) > 1:
    parser.error('Must specify --output if there are multiple trace files.')
  else:
    name_part = os.path.splitext(args.trace_files[0])[0]
    output_filename = name_part + '.html'

  with codecs.open(output_filename, mode='w', encoding='utf-8') as f:
    WriteHTMLForTracesToFile(args.trace_files, f, config_name=args.config_name)

  if not args.quiet:
    print output_filename
  return 0


class ViewerDataScript(generate.ExtraScript):

  def __init__(self, trace_data_string, mime_type):
    super(ViewerDataScript, self).__init__()
    self._trace_data_string = trace_data_string
    self._mime_type = mime_type

  def WriteToFile(self, output_file):
    output_file.write('<script id="viewer-data" type="%s">\n' % self._mime_type)
    compressed_trace = StringIO.StringIO()
    with gzip.GzipFile(fileobj=compressed_trace, mode='w') as f:
      f.write(self._trace_data_string)
    b64_content = base64.b64encode(compressed_trace.getvalue())
    output_file.write(b64_content)
    output_file.write('\n</script>\n')


def WriteHTMLForTraceDataToFile(trace_data_list,
                                title, output_file,
                                config_name=None):
  project = tracing_project.TracingProject()

  if config_name is None:
    config_name = project.GetDefaultConfigName()

  modules = [
      'tracing.trace2html',
      'tracing.extras.importer.gzip_importer',  # Must have for all configs.
      project.GetModuleNameForConfigName(config_name)
  ]

  vulcanizer = project.CreateVulcanizer()
  load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(modules)

  scripts = []
  for trace_data in trace_data_list:
    # If the object was previously decoded from valid JSON data (e.g., in
    # WriteHTMLForTracesToFile), it will be a JSON object at this point and we
    # should re-serialize it into a string. Other types of data will be already
    # be strings.
    if not isinstance(trace_data, basestring):
      trace_data = json.dumps(trace_data)
      mime_type = 'application/json'
    else:
      mime_type = 'text/plain'
    scripts.append(ViewerDataScript(trace_data, mime_type))
  generate.GenerateStandaloneHTMLToFile(
      output_file, load_sequence, title, extra_scripts=scripts)


def WriteHTMLForTracesToFile(trace_filenames, output_file, config_name=None):
  trace_data_list = []
  for filename in trace_filenames:
    with open(filename, 'r') as f:
      trace_data = f.read()
      try:
        trace_data = json.loads(trace_data)
      except ValueError:
        pass
      trace_data_list.append(trace_data)

  title = "Trace from %s" % ','.join(trace_filenames)
  WriteHTMLForTraceDataToFile(trace_data_list, title, output_file, config_name)
