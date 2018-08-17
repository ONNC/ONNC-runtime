#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
from collections import defaultdict
from string import Template

from onnx import defs
from onnx.defs import OpSchema

ONNX_ML = bool(os.getenv('ONNX_ML') == '1')
def should_render_domain(domain):
  if domain == 'ai.onnx.ml' and not ONNX_ML:
    return False
  elif ONNX_ML and domain != 'ai.onnx.ml':
    return False
  return True

def to_camel_case(snake_str, init_upper = True):
    components = snake_str.split('_')
    if init_upper:
        components[0] = ''.join([components[0][0].upper(), components[0][1:]])
    return components[0] + ''.join(''.join([x[0].upper(), x[1:]]) for x in components[1:])

def format_attr_type(attr_type):
    return str(attr_type).rsplit('.', 1)[-1].lower()

def gen_compute_ir_substitution_hash(schema):
  hash = {
    'OperatorName': schema.name,
    'OPERATORNAME': schema.name.upper(),
    'operator_name': schema.name.lower(),
  }

  # ========== Input Output ==============
  def for_io_schema(io_schemas, cb):
    def transform_io_schema(idx, io_schema):
      return {
        'idx': idx,
        'io_name': io_schema.name,
        'option': io_schema.option,
      }
    return [cb(transform_io_schema(idx, io_schema)) for idx, io_schema in enumerate(io_schemas)]

  def io_parameter(prefix, ctype):
    def cb(io_schema):
      if OpSchema.FormalParameterOption.Variadic == io_schema['option']:
        return [
          ',{ctype} * const * restrict {prefix}_{io_name}'.format(prefix=prefix, ctype=ctype, **io_schema),
          ',int32_t {prefix}_{io_name}_ntensor'.format(prefix=prefix, ctype=ctype, **io_schema),
          ',const int32_t * {prefix}_{io_name}_ndim, const int32_t * const * restrict {prefix}_{io_name}_dims'.format(prefix=prefix, ctype=ctype, **io_schema)
        ]
      else:
        return [
          ',{ctype} * restrict {prefix}_{io_name}'.format(prefix=prefix, ctype=ctype, **io_schema),
          ',int32_t {prefix}_{io_name}_ndim, const int32_t * restrict {prefix}_{io_name}_dims'.format(prefix=prefix, ctype=ctype, **io_schema)
        ]
    return cb
  flatten = lambda l: [item for sublist in l for item in sublist]
  # ${input_parameters_float}
  hash['input_parameters_float'] = '\n  '.join(flatten(for_io_schema(schema.inputs, io_parameter('input', 'const float'))))
  # ${output_parameters_float}
  hash['output_parameters_float'] = '\n  '.join(flatten(for_io_schema(schema.outputs, io_parameter('output', 'float'))))
  # ========== end of Input Output ==============

  # ========== Attributes ==============
  attrs = []
  if schema.attributes:
    attrs = [attr for _, attr in sorted(schema.attributes.items())]
  def for_attr(cb):
    def transform_attr(attr):
      return {
        'attr_type': format_attr_type(attr.type),
        'attr_name': attr.name,
      }
    return [cb(transform_attr(attr)) for attr in attrs]

  attr_type_map = {
    'int': 'int32_t',
    'ints': 'int32_t * restrict',
    'string': 'const char * restrict',
    'strings': 'const char ** restrict',
    'float': 'float',
    'floats': 'float * restrict',
    'tensor': 'const void * restrict',
    'graph': 'const void * restrict',
  }
  def attr_cb(attr):
    if attr['attr_type'][-1] == 's':
      attr['attr_type'] = attr_type_map[attr['attr_type']]
      return [
        ',{attr_type} {attr_name}'.format(**attr),
        ',int32_t number_of_{attr_name}'.format(**attr),
      ]
    else:
      attr['attr_type'] = attr_type_map[attr['attr_type']]
      return [
        ',{attr_type} {attr_name}'.format(**attr)
      ]
  hash['attribute_paprameters_float'] = '\n  '.join(flatten(for_attr(attr_cb)))
  # ========== end of Attributes ==============
  return hash

def gen_operator_runtime(operator_schemas, template_filename, dist):
  # TODO: Refactor to simple data structure and simple for loop
  for domain, supportmap in operator_schemas:
    for _, namemap in supportmap:
      for op_type, schema, versions in namemap:
        substitution_hash = gen_compute_ir_substitution_hash(schema)

        template_file = open(template_filename)
        template_str = template_file.read()
        out_file = open(Template(dist).substitute(substitution_hash), 'w')
        out_file.write(Template(template_str).substitute(substitution_hash))
        out_file.close()
        template_file.close()


def gen_runtime_h(operator_schemas, template_filename, dist, operator_path):
  include_operators = []
  # TODO: Refactor to simple data structure and simple for loop
  for domain, supportmap in operator_schemas:
    for _, namemap in supportmap:
      for op_type, schema, versions in namemap:
        substitution_hash = gen_compute_ir_substitution_hash(schema)
        # ${include_operators}
        include_operators.append('#include "{operator_path}/{operator_name}.h"'.format(operator_path=operator_path, **substitution_hash))

  substitution_hash = {
    'include_operators': '\n'.join(include_operators),
  }

  template_file = open(template_filename)
  template_str = template_file.read()
  out_file = open(dist, 'w')
  out_file.write(Template(template_str).substitute(substitution_hash))
  out_file.close()
  template_file.close()
  return

if __name__ == '__main__':
  # domain -> support level -> name -> [schema]
  index = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # type: Dict[Text, Dict[int, Dict[Text, List[OpSchema]]]]
  for schema in defs.get_all_schemas_with_history():
    index[schema.domain][int(schema.support_level)][schema.name].append(schema)

  # Preprocess the Operator Schemas
  # [(domain, [(support_level, [(schema name, current schema, all versions schemas)])])]
  operator_schemas = list()  # type: List[Tuple[Text, List[Tuple[int, List[Tuple[Text, OpSchema, List[OpSchema]]]]]]]
  exsting_ops = set()  # type: Set[Text]
  for domain, _supportmap in sorted(index.items()):
    if not should_render_domain(domain):
      continue

    processed_supportmap = list()
    for _support, _namemap in sorted(_supportmap.items()):
      processed_namemap = list()
      for n, unsorted_versions in sorted(_namemap.items()):
        versions = sorted(unsorted_versions, key=lambda s: s.since_version)
        schema = versions[-1]
        if schema.name in exsting_ops:
          continue
        exsting_ops.add(schema.name)
        processed_namemap.append((n, schema, versions))
      processed_supportmap.append((_support, processed_namemap))
    operator_schemas.append((domain, processed_supportmap))

  # FIXME: Path
  operator_path = "operator"
  output_dir = 'out/'
  if not os.path.exists(output_dir + operator_path):
    os.makedirs(output_dir + 'include/' + operator_path)
    os.makedirs(output_dir + 'lib/' + operator_path)
  gen_runtime_h(operator_schemas, 'onnc-runtime.template.h', output_dir + 'include/onnc-runtime.h', operator_path)
  gen_operator_runtime(operator_schemas, 'operator.template.h', output_dir + 'include/' + operator_path + '/${operator_name}.h')
  gen_operator_runtime(operator_schemas, 'operator.template.c', output_dir + 'lib/' + operator_path + '/${operator_name}.c')
