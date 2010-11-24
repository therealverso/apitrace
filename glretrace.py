##########################################################################
#
# Copyright 2010 VMware, Inc.
# All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
##########################################################################/


import base
import glapi



class ConstRemover(base.Rebuilder):

    def visit_const(self, const):
        return const.type

    def visit_opaque(self, opaque):
        expr = opaque.expr
        if expr.startswith('const '):
            expr = expr[6:]
        return base.Opaque(expr)


class ValueExtractor(base.Visitor):

    def visit_literal(self, literal, lvalue, rvalue):
        print '    %s = %s;' % (lvalue, rvalue)

    def visit_alias(self, alias, lvalue, rvalue):
        self.visit(alias.type, lvalue, rvalue)
    
    def visit_enum(self, enum, lvalue, rvalue):
        print '    %s = %s;' % (lvalue, rvalue)

    def visit_bitmask(self, bitmask, lvalue, rvalue):
        self.visit(bitmask.type, lvalue, rvalue)

    def visit_array(self, array, lvalue, rvalue):
        print '    const Trace::Array *__a%s = dynamic_cast<const Trace::Array *>(&%s);' % (array.id, rvalue)
        print '    if (__a%s) {' % (array.id)
        length = '__a%s->values.size()' % array.id
        print '        %s = new %s[%s];' % (lvalue, array.type, length)
        index = '__i' + array.id
        print '        for(size_t {i} = 0; {i} < {length}; ++{i}) {{'.format(i = index, length = length)
        try:
            self.visit(array.type, '%s[%s]' % (lvalue, index), '*__a%s->values[%s]' % (array.id, index))
        finally:
            print '        }'
            print '    } else {'
            print '        %s = NULL;' % lvalue
            print '    }'
    
    def visit_pointer(self, pointer, lvalue, rvalue):
        # FIXME
        raise NotImplementedError

    def visit_handle(self, handle, lvalue, rvalue):
        self.visit(handle.type, lvalue, "__%s_map[%s]" %(handle.name, rvalue));
        print '    if (verbosity >= 2)'
        print '        std::cout << "%s " << static_cast<%s>(%s) << " <- " << %s << "\\n";' % (handle.name, handle.type, rvalue, lvalue)
    
    def visit_blob(self, blob, lvalue, rvalue):
        print '    %s = static_cast<%s>((%s).blob());' % (lvalue, blob, rvalue)
    
    def visit_string(self, string, lvalue, rvalue):
        print '    %s = (%s)((%s).string());' % (lvalue, string.expr, rvalue)



class ValueWrapper(base.Visitor):

    def visit_literal(self, literal, lvalue, rvalue):
        pass

    def visit_alias(self, alias, lvalue, rvalue):
        self.visit(alias.type, lvalue, rvalue)
    
    def visit_enum(self, enum, lvalue, rvalue):
        pass

    def visit_bitmask(self, bitmask, lvalue, rvalue):
        pass

    def visit_array(self, array, lvalue, rvalue):
        print '    const Trace::Array *__a%s = dynamic_cast<const Trace::Array *>(&%s);' % (array.id, rvalue)
        print '    if (__a%s) {' % (array.id)
        length = '__a%s->values.size()' % array.id
        index = '__i' + array.id
        print '        for(size_t {i} = 0; {i} < {length}; ++{i}) {{'.format(i = index, length = length)
        try:
            self.visit(array.type, '%s[%s]' % (lvalue, index), '*__a%s->values[%s]' % (array.id, index))
        finally:
            print '        }'
            print '    }'
    
    def visit_pointer(self, pointer, lvalue, rvalue):
        # FIXME
        raise NotImplementedError

    def visit_handle(self, handle, lvalue, rvalue):
        print "    __%s_map[static_cast<%s>(%s)] = %s;" % (handle.name, handle.type, rvalue, lvalue)
        print '    if (verbosity >= 2)'
        print '        std::cout << "%s " << static_cast<%s>(%s) << " -> " << %s << "\\n";' % (handle.name, handle.type, rvalue, lvalue)
    
    def visit_blob(self, blob, lvalue, rvalue):
        pass
    
    def visit_string(self, string, lvalue, rvalue):
        pass



def retrace_function(function):
    print 'static void retrace_%s(Trace::Call &call) {' % function.name
    success = True
    for arg in function.args:
        arg_type = ConstRemover().visit(arg.type)
        print '    // %s ->  %s' % (arg.type, arg_type)
        print '    %s %s;' % (arg_type, arg.name)
        rvalue = 'call.arg(%u)' % (arg.index,)
        lvalue = arg.name
        try:
            ValueExtractor().visit(arg_type, lvalue, rvalue)
        except NotImplementedError:
            success = False
            print '    %s = 0; // FIXME' % arg.name
    if not success:
        print '    std::cerr << "warning: unsupported call %s\\n";' % function.name
        print '    return;'
    arg_names = ", ".join([arg.name for arg in function.args])
    if function.type is not base.Void:
        print '    %s __result;' % (function.type)
        print '    __result = %s(%s);' % (function.name, arg_names)
    else:
        print '    %s(%s);' % (function.name, arg_names)
    for arg in function.args:
        if arg.output:
            arg_type = ConstRemover().visit(arg.type)
            rvalue = 'call.arg(%u)' % (arg.index,)
            lvalue = arg.name
            try:
                ValueWrapper().visit(arg_type, lvalue, rvalue)
            except NotImplementedError:
                print '   // FIXME: %s' % arg.name
    if function.type is not base.Void:
        rvalue = '*call.ret'
        lvalue = '__result'
        try:
            ValueWrapper().visit(function.type, lvalue, rvalue)
        except NotImplementedError:
            print '   // FIXME: result'
    print '}'
    print


def retrace_functions(functions):
    for function in functions:
        if function.sideeffects:
            retrace_function(function)

    print 'static bool retrace_call(Trace::Call &call) {'
    for function in functions:
        if not function.sideeffects:
            print '    if (call.name == "%s") {' % function.name
            print '        return true;'
            print '    }'
    print
    print '    if (verbosity >=1 ) {'
    print '        std::cout << call;'
    print '        std::cout.flush();'
    print '    };'
    print
    for function in functions:
        if function.sideeffects:
            print '    if (call.name == "%s") {' % function.name
            print '        retrace_%s(call);' % function.name
            print '        return true;'
            print '    }'
    print '    std::cerr << "warning: unknown call " << call.name << "\\n";'
    print '    return false;'
    print '}'
    print


def retrace_api(api):
    types = api.all_types()

    handles = [type for type in types if isinstance(type, base.Handle)]
    for handle in handles:
        print 'static std::map<%s, %s> __%s_map;' % (handle.type, handle.type, handle.name)
    print

    retrace_functions(api.functions)


if __name__ == '__main__':
    print
    print '#include <stdlib.h>'
    print '#include <string.h>'
    print
    print '#ifdef WIN32'
    print '#include <windows.h>'
    print '#endif'
    print
    print '#include <GL/glew.h>'
    print '#include <GL/glut.h>'
    print
    print '#include "trace_parser.hpp"'
    print
    print 'unsigned verbosity = 0;'
    print
    retrace_api(glapi.glapi)
    print '''

Trace::Parser parser;

static bool insideGlBeginEnd;

static void display(void) {
   Trace::Call *call;

   while ((call = parser.parse_call())) {
      if (call->name == "glFlush" ||
          call->name == "glXSwapBuffers" ||
          call->name == "wglSwapBuffers") {
         glFlush();
         return;
      }
      
      retrace_call(*call);

      if (call->name == "glBegin") {
         insideGlBeginEnd = true;
      }
      
      if (call->name == "glEnd") {
         insideGlBeginEnd = false;
      }

      if (!insideGlBeginEnd) {
         GLenum error = glGetError();
         if (error != GL_NO_ERROR) {
            std::cerr << "warning: glGetError() = ";
            switch (error) {
            case GL_INVALID_ENUM:
               std::cerr << "GL_INVALID_ENUM";
               break;
            case GL_INVALID_VALUE:
               std::cerr << "GL_INVALID_VALUE";
               break;
            case GL_INVALID_OPERATION:
               std::cerr << "GL_INVALID_OPERATION";
               break;
            case GL_STACK_OVERFLOW:
               std::cerr << "GL_STACK_OVERFLOW";
               break;
            case GL_STACK_UNDERFLOW:
               std::cerr << "GL_STACK_UNDERFLOW";
               break;
            case GL_OUT_OF_MEMORY:
               std::cerr << "GL_OUT_OF_MEMORY";
               break;
            case GL_INVALID_FRAMEBUFFER_OPERATION:
               std::cerr << "GL_INVALID_FRAMEBUFFER_OPERATION";
               break;
            case GL_TABLE_TOO_LARGE:
               std::cerr << "GL_TABLE_TOO_LARGE";
               break;
            default:
               std::cerr << error;
               break;
            }
            std::cerr << "\\n";
         }
      }
   }

   glFlush();
   glutIdleFunc(NULL);
}

static void idle(void) {
   glutPostRedisplay();
}

int main(int argc, char **argv)
{
   glutInit(&argc, argv);
   glutInitWindowPosition(0, 0);
   glutInitWindowSize(800, 600);
   glutInitDisplayMode(GLUT_DEPTH | GLUT_RGB | GLUT_SINGLE);
   glutCreateWindow(argv[0]);
   glewInit();

   glutDisplayFunc(&display);
   glutIdleFunc(&idle);

    int i;
    for (i = 1; i < argc; ++i) {
      const char *arg = argv[i];

      if (arg[0] != '-') {
         break;
      }

      if (!strcmp(arg, "--")) {
         break;
      }
      else if (!strcmp(arg, "-v")) {
         ++verbosity;
      } else {
         std::cerr << "error: unknown option " << arg << "\\n";
         return 1;
      }
   }

   for ( ; i < argc; ++i) {
      if (parser.open(argv[i])) {
         glutMainLoop();
         parser.close();
      }
   }

   return 0;
}

'''   