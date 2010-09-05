#  Copyright 2010 Gregory Szorc
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from google.protobuf.descriptor import FieldDescriptor
import re

RE_BARE_BEGIN_BRACKET = re.compile(r'^\s*{\s*$')
RE_BEGIN_BRACKET = re.compile(r'{\s*$')
RE_END_BRACKET = re.compile(r'^\s*};?\s*$')

FIELD_LABEL_MAP = {
    FieldDescriptor.LABEL_OPTIONAL: 'optional',
    FieldDescriptor.LABEL_REQUIRED: 'required',
    FieldDescriptor.LABEL_REPEATED: 'repeated'
}

FIELD_TYPE_MAP = {
    FieldDescriptor.TYPE_DOUBLE: 'double',
    FieldDescriptor.TYPE_FLOAT: 'float',
    FieldDescriptor.TYPE_INT64: 'int64',
    FieldDescriptor.TYPE_UINT64: 'uint64',
    FieldDescriptor.TYPE_INT32: 'int32',
    FieldDescriptor.TYPE_FIXED64: 'fixed64',
    FieldDescriptor.TYPE_FIXED32: 'fixed32',
    FieldDescriptor.TYPE_BOOL: 'bool',
    FieldDescriptor.TYPE_STRING: 'string',
    FieldDescriptor.TYPE_GROUP: 'group',
    FieldDescriptor.TYPE_MESSAGE: 'message',
    FieldDescriptor.TYPE_BYTES: 'bytes',
    FieldDescriptor.TYPE_UINT32: 'uint32',
    FieldDescriptor.TYPE_ENUM: 'enum',
    FieldDescriptor.TYPE_SFIXED32: 'sfixed32',
    FieldDescriptor.TYPE_SFIXED64: 'sfixed64',
    FieldDescriptor.TYPE_SINT32: 'sint32',
    FieldDescriptor.TYPE_SINT64: 'sint64',
}

def lua_protobuf_header():
    '''Returns common header included by all produced files'''
    return '''
#ifndef LUA_PROTOBUF_H
#define LUA_PROTOBUF_H

#include <google/protobuf/message.h>

#ifdef __cplusplus
extern "C" {
#endif

// type for callback function that is executed before Lua performs garbage
// collection on a message instance.
// if called function returns 1, Lua will free the memory backing the object
// if returns 0, Lua will not free the memory
typedef int (*lua_protobuf_gc_callback)(::google::protobuf::Message *msg, void *userdata);

// GC callback function that always returns true
LUA_PROTOBUF_EXPORT int lua_protobuf_gc_always_free(::google::protobuf::Message *msg, void *userdata);

#ifdef __cplusplus
}
#endif

#endif

'''

def lua_protobuf_source():
    '''Returns source for common code'''
    return '''

#include "lua-protobuf.h"

int lua_protobuf_gc_always_free(::google::protobuf::Message *msg, void *ud)
{
    return 1;
}

'''

def c_header_header(filename, package):
    return [
        '// Generated by the lua-protobuf compiler.',
        '// You shouldn\'t be editing this file manually',
        '//',
        '// source proto file: %s' % filename,
        '',
        '#ifndef LUA_PROTOBUF_%s_H' % package.replace('.', '_'),
        '#define LUA_PROTOBUF_%s_H' % package.replace('.', '_'),
        '',
        '#include "lua-protobuf.h"',
        '#include <%s.pb.h>' % package.replace('.', '/'),
        '',
        '#ifdef __cplusplus',
        'extern "C" {',
        '#endif',
        '',
        '#include <lua.h>',
        '',
        '// register all messages in this package to a Lua state',
        'LUA_PROTOBUF_EXPORT int %sopen(lua_State *L);' % package_function_prefix(package),
        '',
    ]

def source_header(filename, package):
    '''Returns lines that begin a source file'''
    return [
        '// Generated by the lua-protobuf compiler',
        '// You shouldn\'t edit this file manually',
        '//',
        '// source proto file: %s' % filename,
        '',
        '#include "%s.pb-lua.h"' % package.replace('.', '/'),
        '',
        '#ifdef __cplusplus',
        'extern "C" { // make sure functions treated with C naming',
        '#endif',
        '',
        '#include <lauxlib.h>',
        '',
        '#ifdef __cplusplus',
        '}',
        '#endif',
        '',
        '#include <string>',
        '',
        '// this represents Lua udata for a protocol buffer message',
        '// we record where a message came from so we can GC it properly',
        'typedef struct msg_udata { // confuse over-simplified pretty-printer',
        '    ::google::protobuf::Message * msg;',
        '    bool lua_owns;',
        '    lua_protobuf_gc_callback gc_callback;',
        '    void * callback_data;',
        '} msg_udata;',
        '',
    ]

def package_function_prefix(package):
    return 'lua_protobuf_%s_' % package.replace('.', '_')

def message_function_prefix(package, message):
    return '%s%s_' % (package_function_prefix(package), message)

def message_open_function(package, message):
    '''Returns function name that registers the Lua library for a message type'''

    return '%sopen' % message_function_prefix(package, message)

def cpp_class(package, message):
    '''Returns the fully qualified class name for a message type'''

    return '::%s::%s' % ( package.replace('.', '::'), message )

def field_function_name(package, message, prefix, field):
    '''Obtain the function name of a field accessor/mutator function'''

    return '%s%s_%s' % ( message_function_prefix(package, message), prefix, field )

def field_function_start(package, message, prefix, field):
    '''Obtain the start of function for a field accessor function'''
    return [
        'int %s(lua_State *L)' % field_function_name(package, message, prefix, field),
        '{',
    ]

def lua_libname(package, message):
    '''Returns the Lua library name for a specific message'''

    return 'protobuf.%s.%s' % (package, message)

def metatable(package, message):
    '''Returns Lua metatable for protocol buffer message type'''
    return 'protobuf_.%s.%s' % (package, message)

def obtain_message_from_udata(package, message, index=1):
    '''Statement that obtains a message from userdata'''

    c = cpp_class(package, message)
    return [
        'msg_udata * ud = (msg_udata *)%s;' % check_udata(package, message, index),
        '%s *m = (%s *)ud->msg;' % ( c, c ),
    ]

def check_udata(package, message, index=1):
    '''Validates a udata is instance of protocol buffer message

    By default, it validates udata at top of the stack
    '''

    return 'luaL_checkudata(L, %d, "%s")' % ( index, metatable(package, message) )

def has_body(package, message, field):
    '''Returns the function body for a has_<field> function'''

    lines = []
    lines.extend(obtain_message_from_udata(package, message))
    lines.append('lua_pushboolean(L, m->has_%s());' % field)
    lines.append('return 1;')

    return lines

def clear_body(package, message, field):
    '''Returns the function body for a clear_<field> function'''
    lines = []
    lines.extend(obtain_message_from_udata(package, message))
    lines.append('m->clear_%s();' % field)
    lines.append('return 0;')

    return lines

def size_body(package, message, field):
    '''Returns the function body for a size_<field> function'''
    lines = []
    lines.extend(obtain_message_from_udata(package, message))
    lines.append('int size = m->%s_size();' % field)
    lines.append('lua_pushinteger(L, size);')
    lines.append('return 1;')

    return lines

def field_get(package, message, field_descriptor):
    '''Returns function definition for a get_<field> function'''

    name = field_descriptor.name
    type = field_descriptor.type
    label = field_descriptor.label
    repeated = label == FieldDescriptor.LABEL_REPEATED

    lines = []
    lines.extend(field_function_start(package, message, 'get', name))
    lines.extend(obtain_message_from_udata(package, message))

    # the logic is significantly different depending on if the field is
    # singular or repeated.
    # for repeated, we have an argument which points to the numeric index to
    # retrieve. in true Lua convention, we index starting from 1, which is
    # different from protocol buffers, which indexes from 0

    if repeated:
        lines.extend([
            'if (lua_gettop(L) != 2) {',
                'return luaL_error(L, "missing required numeric argument");',
            '}',
            'lua_Integer index = luaL_checkinteger(L, 2);',
            'if (index < 1 || index > m->%s_size()) {' % name,
                # TODO is returning nil the more Lua way?
                'return luaL_error(L, "index must be between 1 and current size: %%d", m->%s_size());' % name,
            '}',
        ])

    # TODO float and double types are not equivalent. don't treat them as such
    # TODO figure out how to support 64 bit integers properly

    # TODO support the follwoing
    #   FieldDescriptor.TYPE_GROUP
    #   FieldDescriptor.TYPE_MESSAGE
    #   FieldDescriptor.TYPE_ENUM

    if repeated:
        if type in [ FieldDescriptor.TYPE_STRING, FieldDescriptor.TYPE_BYTES ]:
            lines.extend([
                'string s = m->%s(index - 1);' % name,
                'lua_pushlstring(L, s.c_str(), s.size());',
            ])
        elif type == FieldDescriptor.TYPE_BOOL:
            lines.append('lua_pushboolean(L, m->%s(index-1));' % name)

        elif type in [FieldDescriptor.TYPE_INT32, FieldDescriptor.TYPE_UINT32,
            FieldDescriptor.TYPE_FIXED32, FieldDescriptor.TYPE_SFIXED32, FieldDescriptor.TYPE_SINT32]:

            lines.append('lua_pushinteger(L, m->%s(index-1));' % name)

        elif type in [ FieldDescriptor.TYPE_INT64, FieldDescriptor.TYPE_UINT64,
            FieldDescriptor.TYPE_FIXED64, FieldDescriptor.TYPE_SFIXED64, FieldDescriptor.TYPE_SINT64]:
            lines.append('lua_pushinteger(L, m->%s(index-1));' % name)

        elif type == FieldDescriptor.TYPE_FLOAT or type == FieldDescriptor.TYPE_DOUBLE:
            lines.append('lua_pushnumber(L, m->%s(index-1));' % name)

        else:
            lines.append('return luaL_errorL, "lua-protobuf does not support this field type");')
    else:
        # for scalar fields, we push nil if the value is not defined
        # this is the Lua way
        if type == FieldDescriptor.TYPE_STRING or type == FieldDescriptor.TYPE_BYTES:
            lines.append('string s = m->%s();' % name)
            lines.append('m->has_%s() ? lua_pushlstring(L, s.c_str(), s.size()) : lua_pushnil(L);' % name)

        elif type == FieldDescriptor.TYPE_BOOL:
            lines.append('m->has_%s() ? lua_pushboolean(L, m->%s()) : lua_pushnil(L);' % ( name, name ))

        elif type in [FieldDescriptor.TYPE_INT32, FieldDescriptor.TYPE_UINT32,
            FieldDescriptor.TYPE_FIXED32, FieldDescriptor.TYPE_SFIXED32, FieldDescriptor.TYPE_SINT32]:
            lines.append('m->has_%s() ? lua_pushinteger(L, m->%s()) : lua_pushnil(L);' % ( name, name ))

        elif type in [ FieldDescriptor.TYPE_INT64, FieldDescriptor.TYPE_UINT64,
            FieldDescriptor.TYPE_FIXED64, FieldDescriptor.TYPE_SFIXED64, FieldDescriptor.TYPE_SINT64]:
            lines.append('m->has_%s() ? lua_pushinteger(L, m->%s()) : lua_pushnil(L);' % ( name, name ))

        elif type == FieldDescriptor.TYPE_FLOAT or type == FieldDescriptor.TYPE_DOUBLE:
            lines.append('m->has_%s() ? lua_pushnumber(L, m->%s()) : lua_pushnil(L);' % ( name, name ))

        else:
            # not supported yet :(
            lines.append('return luaL_error(L, "lua-protobuf does not support this field type");')

    lines.append('return 1;')
    lines.append('}\n')

    return lines

def field_set_assignment(field, args):
    return [
        'if (index == current_size + 1) {',
            'm->add_%s(%s);' % ( field, args ),
        '}',
        'else {',
            'm->set_%s(index-1, %s);' % ( field, args ),
        '}',
    ]

def field_set(package, message, field_descriptor):
    '''Returns function definition for a set_<field> function'''

    name = field_descriptor.name
    type = field_descriptor.type
    label = field_descriptor.label
    repeated = label == FieldDescriptor.LABEL_REPEATED

    lines = []
    lines.extend(field_function_start(package, message, 'set', name))
    lines.extend(obtain_message_from_udata(package, message, 1))

    # we do things differently depending on if this is a singular or repeated field
    # for singular fields, the new value is the first argument
    # for repeated fields, the index is arg1 and the value is arg2
    if repeated:
        lines.extend([
            'if (lua_gettop(L) != 3) {',
            '    return luaL_error(L, "required 2 arguments not passed to function");',
            '}',
            'lua_Integer index = luaL_checkinteger(L, 2);',
            'size_t current_size = m->%s_size();' % name,
            'if (index < 1 || index > current_size + 1) {',
                'return luaL_error(L, "index must be between 1 and %d", current_size + 1);',
            '}',

            # we don't support the automagic nil clears value... yet
            'if (lua_isnil(L, 3)) {',
                'return luaL_error(L, "cannot assign nil to repeated fields (yet)");',
            '}',
        ])

    # TODO proper 64 bit handling

    # TODO support following types
    #    FieldDescriptor.TYPE_GROUP
    #    FieldDescriptor.TYPE_MESSAGE
    #    FieldDescriptor.TYPE_ENUM

    # now move on to the assignment
    if repeated:
        if type in [ FieldDescriptor.TYPE_STRING, FieldDescriptor.TYPE_BYTES ]:
            lines.extend([
                'size_t length = 0;',
                'const char *s = luaL_checklstring(L, 3, &length);',
            ])
            lines.extend(field_set_assignment(name, 's, length'))

        elif type == FieldDescriptor.TYPE_BOOL:
            lines.append('bool b = lua_toboolean(L, 3);')
            lines.extend(field_set_assignment(name, 'b'))

        elif type in [ FieldDescriptor.TYPE_DOUBLE, FieldDescriptor.TYPE_FLOAT ]:
            lines.append('double d = lua_tonumber(L, 3);')
            lines.extend(field_set_assignment(name, 'd'))

        elif type in [ FieldDescriptor.TYPE_INT32, FieldDescriptor.TYPE_FIXED32,
            FieldDescriptor.TYPE_UINT32, FieldDescriptor.TYPE_SFIXED32, FieldDescriptor.TYPE_SINT32 ]:

            lines.append('lua_Integer i = lua_tointeger(L, 3);')
            lines.extend(field_set_assignment(name, 'i'))

        elif type in [ FieldDescriptor.TYPE_INT64, FieldDescriptor.TYPE_UINT64,
            FieldDescriptor.TYPE_FIXED64, FieldDescriptor.TYPE_SFIXED64, FieldDescriptor.TYPE_SINT64]:

            lines.append('lua_Integer i = lua_tointeger(L, 3);')
            lines.extend(field_set_assignment(name, 'i'))
        else:
            lines.append('return luaL_error(L, "field type not yet supported");')

        lines.append('return 0;')
    else:
        # if they call set() with nil, we interpret as a clear
        # this is the Lua way, after all
        lines.extend([
            'if (lua_isnil(L, 2)) {',
                'm->clear_%s();' % name,
                'return 0;',
            '}',
            '',
        ])

        if type in [ FieldDescriptor.TYPE_STRING, FieldDescriptor.TYPE_BYTES ]:
            lines.extend([
                'if (!lua_isstring(L, 2)) return luaL_error(L, "passed value is not a string");',
                'size_t len;',
                'const char *s = lua_tolstring(L, 2, &len);',
                'if (!s) {',
                    'luaL_error(L, "could not obtain string on stack. weird");',
                '}',
                'm->set_%s(s, len);' % name,
                'return 0;',
            ])

        elif type in [ FieldDescriptor.TYPE_DOUBLE, FieldDescriptor.TYPE_FLOAT ]:
            lines.extend([
                'if (!lua_isnumber(L, 2)) return luaL_error(L, "passed value cannot be converted to a number");',
                'lua_Number n = lua_tonumber(L, 2);',
                'm->set_%s(n);' % name,
                'return 0;',
            ])

        elif type in [ FieldDescriptor.TYPE_INT32, FieldDescriptor.TYPE_FIXED32,
            FieldDescriptor.TYPE_UINT32, FieldDescriptor.TYPE_SFIXED32, FieldDescriptor.TYPE_SINT32 ]:

            lines.extend([
                'lua_Integer v = luaL_checkinteger(L, 2);',
                'm->set_%s(v);' % name,
                'return 0;',
            ])

        elif type in [ FieldDescriptor.TYPE_INT64, FieldDescriptor.TYPE_UINT64,
            FieldDescriptor.TYPE_FIXED64, FieldDescriptor.TYPE_SFIXED64, FieldDescriptor.TYPE_SINT64]:

            lines.extend([
                'lua_Integer i = luaL_checkinteger(L, 2);',
                'm->set_%s(i);' % name,
                'return 0;',
            ])

        elif type == FieldDescriptor.TYPE_BOOL:
            lines.extend([
                'bool b = lua_toboolean(L, 2);',
                'm->set_%s(b);' % name,
                'return 0;',
            ])

        else:
            lines.append('return luaL_error(L, "field type is not yet supported");')

    lines.append('}\n')

    return lines

def new_message(package, message):
    '''Returns function definition for creating a new protocol buffer message'''

    lines = []

    lines.append('int %snew(lua_State *L)' % message_function_prefix(package, message))
    lines.append('{')

    c = cpp_class(package, message)
    lines.append('msg_udata * ud = (msg_udata *)lua_newuserdata(L, sizeof(msg_udata));')

    lines.append('ud->lua_owns = true;')
    lines.append('ud->msg = new %s();' % c)
    lines.append('ud->gc_callback = NULL;')
    lines.append('ud->callback_data = NULL;')

    lines.append('luaL_getmetatable(L, "%s");' % metatable(package, message))
    lines.append('lua_setmetatable(L, -2);')
    lines.append('return 1;')

    lines.append('}\n')

    return lines

def message_pushcopy_function(package, message):
    '''Returns function definition for pushing a copy of a message to the stack'''

    return [
        'bool %spushcopy(lua_State *L, const %s &from)' % ( message_function_prefix(package, message), cpp_class(package, message) ),
        '{',
        'msg_udata * ud = (msg_udata *)lua_newuserdata(L, sizeof(msg_udata));',
        'ud->lua_owns = true;',
        'ud->msg = new %s(from);' % cpp_class(package, message),
        'ud->gc_callback = NULL;',
        'ud->callback_data = NULL;',
        'luaL_getmetatable(L, "%s");' % metatable(package, message),
        'lua_setmetatable(L, -2);',
        'return true;',
        '}',
    ]

def message_pushreference_function(package, message):
    '''Returns function definition for pushing a reference of a message on the stack'''

    return [
        'bool %spushreference(lua_State *L, %s *msg, lua_protobuf_gc_callback f, void *data)' % ( message_function_prefix(package, message), cpp_class(package, message) ),
        '{',
        'msg_udata * ud = (msg_udata *)lua_newuserdata(L, sizeof(msg_udata));',
        'ud->lua_owns = false;',
        'ud->msg = msg;',
        'ud->gc_callback = f;',
        'ud->callback_data = data;',
        'luaL_getmetatable(L, "%s");' % metatable(package, message),
        'lua_setmetatable(L, -2);',
        'return true;',
        '}',
    ]

def parsefromstring_message_function(package, message):
    '''Returns function definition for parsing a message from a serialized string'''

    lines = []

    lines.append('int %sparsefromstring(lua_State *L)' % message_function_prefix(package, message))
    lines.append('{')

    # TODO implement
    lines.append('assert(0);')
    lines.append('return 1;')
    lines.append('}')

    return lines

def gc_message_function(package, message):
    '''Returns function definition for garbage collecting a message'''

    lines = [
        'int %sgc(lua_State *L)' % message_function_prefix(package, message),
        '{',
    ]
    lines.extend(obtain_message_from_udata(package, message, 1))
    # if Lua "owns" the message, we delete it
    # else, we delete only if a callback exists and it says it is OK
    lines.extend([
        'if (ud->lua_owns) {',
        'delete ud->msg;',
        'ud->msg = NULL;',
        'return 0;',
        '}',
        '',
        'if (ud->gc_callback && ud->gc_callback(m, ud->callback_data)) {',
        'delete ud->msg;',
        'ud->msg = NULL;',
        'return 0;',
        '}',
        'return 0;',
        '}',
    ])

    return lines

def clear_message_function(package, message):
    '''Returns the function definition for clearing a message'''

    lines = [
        'int %sclear(lua_State *L)' % message_function_prefix(package, message),
        '{'
    ]
    lines.extend(obtain_message_from_udata(package, message, 1))
    lines.extend([
        'm->Clear();',
        'return 0;',
        '}',
    ])

    return lines

def serialized_message_function(package, message):
    '''Returns the function definition for serializing a message'''

    lines = [
        'int %sserialized(lua_State *L)' % message_function_prefix(package, message),
        '{'
    ]
    lines.extend(obtain_message_from_udata(package, message, 1))
    lines.extend([
        'string s;',
        'if (!m->SerializeToString(&s)) {',
        'return luaL_error(L, "error serializing message");',
        '}',
        'lua_pushlstring(L, s.c_str(), s.length());',
        'return 1;',
        '}',
    ])

    return lines

def message_function_array(package, message):
    '''Defines functions for Lua object type

    These are defined on the Lua metatable for the message type.
    These are basically constructors and static methods in Lua land.
    '''
    return [
        'static const struct luaL_Reg %s_functions [] = {' % message,
        '{"new", %snew},' % message_function_prefix(package, message),
        '{"parsefromstring", %sparsefromstring},' % message_function_prefix(package, message),
        '{NULL, NULL}',
        '};\n',
    ]

def message_method_array(package, descriptor):
    '''Defines functions for Lua object instances

    These are functions available to each instance of a message.
    They take the object userdata as the first parameter.
    '''

    message = descriptor.name
    fp = message_function_prefix(package, message)

    lines = []
    lines.append('static const struct luaL_Reg %s_methods [] = {' % message)
    lines.append('{"serialized", %sserialized},' % fp)
    lines.append('{"clear", %sclear},' % fp)
    lines.append('{"__gc", %sgc},' % message_function_prefix(package, message))

    for fd in descriptor.field:
        name = fd.name
        label = fd.label

        lines.append('{"clear_%s", %s},' % ( name, field_function_name(package, message, 'clear', name) ))
        lines.append('{"get_%s", %s},' % ( name, field_function_name(package, message, 'get', name) ))
        lines.append('{"set_%s", %s},' % ( name, field_function_name(package, message, 'set', name) ))

        if label in [ FieldDescriptor.LABEL_REQUIRED, FieldDescriptor.LABEL_OPTIONAL ]:
            lines.append('{"has_%s", %s},' % ( name, field_function_name(package, message, 'has', name) ))

        if label == FieldDescriptor.LABEL_REPEATED:
            lines.append('{"size_%s", %s},' % ( name, field_function_name(package, message, 'size', name) ))

    lines.append('{NULL, NULL},')
    lines.append('};\n')

    return lines

def message_open(package, message):
    '''Function definition for opening/registering a message type'''

    return [
        'int %s(lua_State *L)' % message_open_function(package, message),
        '{',
        'luaL_newmetatable(L, "%s");' % metatable(package, message),
        'lua_pushvalue(L, -1);',
        'lua_setfield(L, -2, "__index");',
        'luaL_register(L, NULL, %s_methods);' % message,
        'luaL_register(L, "%s", %s_functions);' % (lua_libname(package, message), message),
        'return 1;',
        '}',
        '\n',
    ]

def message_header(package, message_descriptor):
    '''Returns the lines for a header definition of a message'''

    message_name = message_descriptor.name

    lines = []
    lines.append('// Message %s' % message_name)

    function_prefix = 'lua_protobuf_' + package.replace('.', '_') + '_'
    c = cpp_class(package, message_name)

    lines.extend([
        '// registers the message type with Lua',
        'LUA_PROTOBUF_EXPORT int %s(lua_State *L);\n' % message_open_function(package, message_name),
        '',
        '// push a copy of the message to the Lua stack',
        '// caller is free to use original message however she wants, but changes will not',
        '// be reflected in Lua and vice-verse',
        'LUA_PROTOBUF_EXPORT bool %s%s_pushcopy(lua_State *L, const %s &msg);' % ( function_prefix, message_name, c),
        '',
        '// push a reference of the message to the Lua stack',
        '// the 3rd and 4th arguments define a callback that can be invoked just before Lua',
        '// garbage collects the message. If the 3rd argument is NULL, Lua will *NOT* free',
        '// memory. If the second argument points to a function, that function is called when',
        '// Lua garbage collects the object. The function is sent a pointer to the message being',
        '// collected and the 4th argument to this function. If the function returns true,',
        '// Lua will free the memory. If false (0), Lua will not free the memory.',
        'LUA_PROTOBUF_EXPORT bool %s%s_pushreference(lua_State *L, %s *msg, lua_protobuf_gc_callback callback, void *data);' % ( function_prefix, message_name, c ),
        '',
        '',
        '// The following functions are called by Lua. Many people will not need them,',
        '// but they are exported for those that do.',
        '',
        '',
        '// constructor called from Lua',
        'LUA_PROTOBUF_EXPORT int %s%s_new(lua_State *L);' % ( function_prefix, message_name ),
        '',
        '// obtain instance from a serialized string',
        'LUA_PROTOBUF_EXPORT int %s%s_parsefromstring(lua_State *L);' % ( function_prefix, message_name ),
        '',
        '// garbage collects message instance in Lua',
        'LUA_PROTOBUF_EXPORT int %s%s_gc(lua_State *L);' % ( function_prefix, message_name ),
        '',
        '// obtain serialized representation of instance',
        'LUA_PROTOBUF_EXPORT int %s%s_serialized(lua_State *L);' % ( function_prefix, message_name ),
        '',
        '// clear all fields in the message',
        'LUA_PROTOBUF_EXPORT int %s%s_clear(lua_State *L);' % ( function_prefix, message_name ),
        '',
    ])

    # each field defined in the message
    for field_descriptor in message_descriptor.field:
        field_name = field_descriptor.name
        field_number = field_descriptor.number
        field_label = field_descriptor.label
        field_type = field_descriptor.type
        field_default = field_descriptor.default_value

        if field_label not in FIELD_LABEL_MAP.keys():
            raise Exception('unknown field label constant: %s' % field_label)

        field_label_s = FIELD_LABEL_MAP[field_label]

        if field_type not in FIELD_TYPE_MAP.keys():
            raise Exception('unknown field type: %s' % field_type)

        field_type_s = FIELD_TYPE_MAP[field_type]

        lines.append('// %s %s %s = %d' % (field_label_s, field_type_s, field_name, field_number))
        lines.append('LUA_PROTOBUF_EXPORT int %s%s_clear_%s(lua_State *L);' % (function_prefix, message_name, field_name))
        lines.append('LUA_PROTOBUF_EXPORT int %s%s_get_%s(lua_State *L);' % (function_prefix, message_name, field_name))
        lines.append('LUA_PROTOBUF_EXPORT int %s%s_set_%s(lua_State *L);' % (function_prefix, message_name, field_name))

        if field_label in [ FieldDescriptor.LABEL_REQUIRED, FieldDescriptor.LABEL_OPTIONAL ]:
            lines.append('LUA_PROTOBUF_EXPORT int %s%s_has_%s(lua_State *L);' % (function_prefix, message_name, field_name))

        if field_label == FieldDescriptor.LABEL_REPEATED:
            lines.append('LUA_PROTOBUF_EXPORT int %s%s_size_%s(lua_State *L);' % (function_prefix, message_name, field_name))

        lines.append('')

    lines.append('// end of message %s\n' % message_name)

    return lines


def message_source(package, message_descriptor):
    '''Returns lines of source code for an individual message type'''
    lines = []

    message = message_descriptor.name

    lines.extend(message_function_array(package, message))
    lines.extend(message_method_array(package, message_descriptor))
    lines.extend(message_open(package, message))
    lines.extend(message_pushcopy_function(package, message))
    lines.extend(message_pushreference_function(package, message))
    lines.extend(new_message(package, message))
    lines.extend(parsefromstring_message_function(package, message))
    lines.extend(gc_message_function(package, message))
    lines.extend(clear_message_function(package, message))
    lines.extend(serialized_message_function(package, message))

    for descriptor in message_descriptor.field:
        name = descriptor.name

        # clear() is in all label types
        lines.extend(field_function_start(package, message, 'clear', name))
        lines.extend(clear_body(package, message, name))
        lines.append('}\n')

        lines.extend(field_get(package, message, descriptor))
        lines.extend(field_set(package, message, descriptor))

        if descriptor.label in [FieldDescriptor.LABEL_OPTIONAL, FieldDescriptor.LABEL_REQUIRED]:
            # has_<field>()
            lines.extend(field_function_start(package, message, 'has', name))
            lines.extend(has_body(package, message, name))
            lines.append('}\n')

        if descriptor.label == FieldDescriptor.LABEL_REPEATED:
            # size_<field>()
            lines.extend(field_function_start(package, message, 'size', name))
            lines.extend(size_body(package, message, name))
            lines.append('}\n')


    return lines

def file_header(file_descriptor):

    filename = file_descriptor.name
    package = file_descriptor.package

    lines = []

    lines.extend(c_header_header(filename, package))

    for descriptor in file_descriptor.message_type:
        lines.extend(message_header(package, descriptor))

    lines.append('#ifdef __cplusplus')
    lines.append('}')
    lines.append('#endif')
    lines.append('')
    lines.append('#endif')

    return '\n'.join(lines)

def file_source(file_descriptor):
    '''Obtains the source code for a FileDescriptor instance'''

    filename = file_descriptor.name
    package = file_descriptor.package

    lines = []
    lines.extend(source_header(filename, package))
    lines.append('using ::std::string;\n')

    lines.append('int %sopen(lua_State *L)' % package_function_prefix(package))
    lines.append('{')
    for descriptor in file_descriptor.message_type:
        lines.append('%s(L);' % message_open_function(package, descriptor.name))
    lines.append('return 1;')
    lines.append('}')
    lines.append('\n')

    for descriptor in file_descriptor.message_type:
        lines.extend(message_source(package, descriptor))

    # perform some hacky pretty-printing
    formatted = []
    indent = 0
    for line in lines:
        if RE_BARE_BEGIN_BRACKET.search(line):
            formatted.append((' ' * indent) + line)
            indent += 4
        elif RE_BEGIN_BRACKET.search(line):
            formatted.append((' ' * indent) + line)
            indent += 4
        elif RE_END_BRACKET.search(line):
            if indent >= 4:
                indent -= 4
            formatted.append((' ' * indent) + line)
        else:
            formatted.append((' ' * indent) + line)

    return '\n'.join(formatted)

