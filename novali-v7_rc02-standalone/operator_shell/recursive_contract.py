"""Dependency-free validation for the small runtime-owned curriculum grammar."""
import math
import re


def validate(value, schema, path='$'):
    allowed={'anyOf','type','const','enum','properties','required','additionalProperties','maxProperties',
             'items','minItems','maxItems','uniqueItems','minimum','maximum','minLength','maxLength','pattern','description'}
    if set(schema)-allowed:raise ValueError('unsupported_curriculum_schema_keyword')
    def require(condition, reason):
        if not condition:raise ValueError(path+': '+reason)
    if 'anyOf' in schema:
        errors=[]
        for branch in schema['anyOf']:
            try:validate(value,branch,path);break
            except ValueError as exc:errors.append(str(exc))
        else:raise ValueError(path+': no permitted alternative; '+ '; '.join(errors[:2]))
    if 'const' in schema:require(value==schema['const'] and type(value)==type(schema['const']),'binding differs')
    if 'enum' in schema:require(any(value==v and type(value)==type(v) for v in schema['enum']),'not an offered choice')
    kind=schema.get('type')
    types={'object':dict,'array':list,'string':str,'integer':int,'number':(int,float),'boolean':bool,'null':type(None)}
    if kind:
        require(kind in types,'unsupported type')
        require(isinstance(value,types[kind]) and not (kind in {'integer','number'} and type(value) is bool),'wrong type')
    if kind=='object':
        properties=schema.get('properties',{})
        require(set(schema.get('required',[]))<=set(value),'required fields missing')
        require(len(value)<=schema.get('maxProperties',1000),'too many properties')
        extras=set(value)-set(properties);additional=schema.get('additionalProperties',True)
        require(additional is not False or not extras,'unexpected fields')
        for key,item in value.items():
            require(isinstance(key,str),'string keys required')
            if key in properties:validate(item,properties[key],path+'/'+key)
            elif isinstance(additional,dict):validate(item,additional,path+'/'+key)
    if kind=='array':
        require(schema.get('minItems',0)<=len(value)<=schema.get('maxItems',10**6),'array bounds')
        if schema.get('uniqueItems'):require(all(v not in value[:i] for i,v in enumerate(value)),'distinct items required')
        for i,item in enumerate(value):validate(item,schema['items'],path+'/'+str(i))
    if kind=='string':
        require(schema.get('minLength',0)<=len(value)<=schema.get('maxLength',10**6),'text bounds')
        if 'pattern' in schema:require(re.search(schema['pattern'],value) is not None,'text pattern')
    if kind in {'integer','number'}:
        require(math.isfinite(value),'finite number required')
        require(schema.get('minimum',-math.inf)<=value<=schema.get('maximum',math.inf),'numeric bounds')
