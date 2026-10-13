"""Resolve declared parameters only; never mutate a pinned graph."""
from dataclasses import dataclass
from fractions import Fraction
import secrets
from .workflow_schemas import WorkflowError, canonical, strict_json, digest, matches_type, validate_literal, raw_input_contract

@dataclass(frozen=True)
class ResolvedParameters:
    canonical_values: str
    canonical_prompt: str
    resolved_prompt_sha256: str
    @property
    def values(self): return strict_json(self.canonical_values)
    @property
    def api_prompt(self): return strict_json(self.canonical_prompt)


def resolve_parameters(bundle, values):
    if not isinstance(values,dict): raise WorkflowError('Parameter values must be object')
    bindings=bundle.manifest['parameter_bindings']; known={b['semantic_name'] for b in bindings}
    if set(values)-known: raise WorkflowError('Undeclared parameter')
    graph=bundle.api_prompt; resolved={}
    for b in bindings:
        name=b['semantic_name']; value=values.get(name,b.get('default',graph[b['node_id']]['inputs'][b['input_name']]))
        if value=='random' and b.get('random') is True:
            if b['type']!='INT' or type(b.get('min')) is not int or type(b.get('max')) is not int: raise WorkflowError('Random requires bounded integer contract')
            value=b['min']+secrets.randbelow(b['max']-b['min']+1)
        if not matches_type(value,b['type']): raise WorkflowError('Parameter type mismatch: '+name)
        if 'min' in b and value<b['min'] or 'max' in b and value>b['max']: raise WorkflowError('Parameter out of range: '+name)
        if 'choices' in b and value not in b['choices']: raise WorkflowError('Parameter choice invalid: '+name)
        if 'multiple' in b and (type(b['multiple']) is not int or b['multiple']<=0 or type(value) is not int or value%b['multiple']): raise WorkflowError('Parameter multiple invalid: '+name)
        schema=next(r for r in bundle.manifest['node_requirements'] if r['class_type']==graph[b['node_id']]['class_type'])
        validate_literal(value,b['type'],raw_input_contract(schema,b['input_name']))
        resolved[name]=value; graph[b['node_id']]['inputs'][b['input_name']]=value
    shape=bundle.manifest.get('shape_constraints',{})
    if shape:
        allowed={'width','height','frames','fps_numerator','fps_denominator','duration_numerator','duration_denominator','max_pixels','max_pixel_frames','frame_multiple','frame_offset','endpoint_convention'}
        if not isinstance(shape,dict) or set(shape)-allowed: raise WorkflowError('Unsupported shape constraints')
        def v(key):
            if key not in shape or shape[key] not in resolved: raise WorkflowError('Missing shape parameter: '+key)
            x=resolved[shape[key]]
            if type(x) is not int or x<=0: raise WorkflowError('Shape values must be positive integers')
            return x
        if 'width' in shape or 'height' in shape:
            pixels=v('width')*v('height')
            if type(shape.get('max_pixels')) is not int or pixels>shape['max_pixels']: raise WorkflowError('Pixel budget exceeded or missing')
            if 'frames' in shape and (type(shape.get('max_pixel_frames')) is not int or pixels*v('frames')>shape['max_pixel_frames']): raise WorkflowError('Pixel-frame budget exceeded or missing')
        if 'frame_multiple' in shape:
            multiple=shape['frame_multiple']; offset=shape.get('frame_offset',0)
            if type(multiple) is not int or multiple<=0 or type(offset) is not int or (v('frames')-offset)%multiple: raise WorkflowError('Frame multiple violated')
        if 'fps_numerator' in shape or 'fps_denominator' in shape:
            fps=Fraction(v('fps_numerator'),v('fps_denominator'))
            if 'duration_numerator' in shape:
                duration=Fraction(v('duration_numerator'),v('duration_denominator'))
                if shape.get('endpoint_convention')!='half_open_exact' or duration*fps != v('frames'): raise WorkflowError('Exact duration/frame contract violated')
    return ResolvedParameters(canonical(resolved),canonical(graph),digest(graph))
