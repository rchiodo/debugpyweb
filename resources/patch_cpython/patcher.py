import argparse
import re
import shutil
import os

pre_run_code = """
var CustomSockets = {
    counter: 0,
    sync_api: undefined,
    connection: undefined,
    root: undefined,
    next_name: function () {
        CustomSockets.counter += 1;
        return `socket${CustomSockets.counter}`;
    },
    init: function() {
        if (CustomSockets.sync_api == undefined) {
            CustomSockets.sync_api = require('@vscode/sync-api-common/node');
            const { isMainThread, parentPort } = require('node:worker_threads');
            if (isMainThread) {
                throw new Error(`CustomSockets have to be mounted on a worker thread`);
            }
            // Setup our connection
            CustomSockets.connection = new CustomSockets.sync_api.ClientConnection(parentPort);
            CustomSockets.root = FS.mount(CustomSockets, {}, null);
        }
    },
    mount: function () {
        // return a root node
        return FS.createNode(null, '/', 49152, 0);
    },
    getBuffer: function(src, len) {
        return GROWABLE_HEAP_U8().slice(src, src+len);
    },
    copyBuffer: function(src, dest, offset, len) {
        var minLen = Math.min(src.length, len);
        GROWABLE_HEAP_U8().set(src.slice(0, minLen), dest+offset);
        return minLen;
    },
    stream_ops: {
        poll: function (stream) {
            return 0;
        },
        ioctl: function (stream, request, varargs) {
            return 0;
        },
        read: function (stream, buffer, offset, length, position /* ignored */) {
            CustomSockets.init();
            var result = CustomSockets.connection.sendRequest('socket/read', { length }, new CustomSockets.sync_api.VariableResult("binary"));
            if (result.errno !== 0) {
                return -1;
            }
            return CustomSockets.copyBuffer(result.data, buffer, offset, length);
        },
        write: function (stream, buffer, offset, length, position /* ignored */) {
            CustomSockets.init();
            var result = CustomSockets.connection.sendRequest('socket/write', { buffer: CustomSockets.getBuffer(buffer, length) }, new CustomSockets.sync_api.VariableResult("binary"));
            if (result.errno !== 0) {
                return -1;
            }
            return length;
        },
        close: function (stream) {
            CustomSockets.init();
            CustomSockets.connection.sendRequest('socket/close', {}, new CustomSockets.sync_api.VariableResult("binary"));
            return 0;
        }
    }
}

function create_custom_socket() {
    CustomSockets.init();
    var name = CustomSockets.next_name();
    var node = FS.createNode(CustomSockets.root, name, 49152, 0)
    var sock = {};
    var stream = FS.createStream({ path: name, node: node, flags: 2, seekable: false, stream_ops: CustomSockets.stream_ops })
    sock.stream = stream;
    node.sock = sock;
    return sock;
}

function get_socket_from_fd(fd) {
    var stream = FS.getStream(fd)
    return stream.node.sock;
}
"""
syscall_bind = """
function ___syscall_bind(fd, addr, addrlen) {
    console.log("syscall_bind");
    // Binding address to the file descriptor
    var info = getSocketAddress(addr, addrlen);
    var socket = get_socket_from_fd(fd);
    socket.info = info;
    return 0;
}
"""
syscall_listen = """
function ___syscall_listen(fd, backlog) {
    console.log("syscall_listen");
    // Indicates the fd should be waiting for accept
    var current = FS.getStream(fd);
    current.should_listen = true;
    return 0;
}
"""
syscall_socket = """
function ___syscall_socket(domain, type, protocol) {
    console.log("syscall_socket");
    // Creating the fd for the type of socket
    var sock = create_custom_socket();
    sock.domain = domain;
    sock.type = type;
    sock.protocol = protocol;

    // file descriptor is handled by the FS 
    return sock.stream.fd;
}
"""
syscall_accept4 = """
function ___syscall_accept4(fd, addr, addrlen, flags) {
    console.log("syscall_accept4");
    // Returns a new socket
    var newSock = create_custom_socket();
    var current = get_socket_from_fd(fd);
    if (addr !== 0 && current.info) {
        writeSockaddr(addr, current.info.family, current.info.addr, current.info.port, addrlen);
    }
    return newSock.stream.fd;
}
"""
syscall_connect = """
function ___syscall_connect(fd,addr,addrlen) {
    console.log("syscall_connect");
    // Connects client side to a socket
    var current = get_socket_from_fd(fd);
    if (addr !== 0) {
        var info = getSocketAddress(addr, addrlen);
        current.info = info;
    }
    // Don't need to do anything here as we're already connected
    // Might want to read the address information to determine if
    // should use custom sockets or default back to web
    return 0;
}
"""
syscall_getsockname = """
function ___syscall_getsockname(fd,addr,addrlen) {
    console.log("syscall_getsockname");
    var current = get_socket_from_fd(fd);
    if (current && current.info) {
        writeSockaddr(addr, current.info.family, current.info.addr, current.info.port, addrlen);
    }
    return 0;
}
"""
syscall_recvfrom = """
function ___syscall_recvfrom(fd, buf, len, flags, addr, addrlen) {
    console.log("syscall_recvfrom");
    CustomSockets.init();
    // Should block trying to receive data from the other side
    var result = CustomSockets.connection.sendRequest(`socket/recvfrom`, { length: len }, new CustomSockets.sync_api.VariableResult("binary"));
    var current = get_socket_from_fd(fd);
    if (addr !== 0 && current.info) {
        writeSockaddr(addr, current.info.family, current.info.addr, current.info.port, addrlen);
    }
    return CustomSockets.copyBuffer(result.data, buf, 0, len);
}
"""
doWritev = """
var printCharBuffers = [null,[],[]];
// Create our own out/err so we work inside a VS code extension host
var printStdout = process.stdout.write.bind(process.stdout);
var printStderr = process.stderr.write.bind(process.stderr);
function printChar(stream, curr) {
  var buffer = printCharBuffers[stream];
  var logFunc = stream === 1 ? printStdout : printStderr;
  if (curr === 0) {
    logFunc(UTF8ArrayToString(buffer, 0));
    buffer.length = 0;
  } else {
    buffer.push(curr);
  }
}

function doWritev(stream, iov, iovcnt, offset) {
 var ret = 0;
 for (var i = 0; i < iovcnt; i++) {
  var ptr = GROWABLE_HEAP_U32()[iov >> 2];
  var len = GROWABLE_HEAP_U32()[iov + 4 >> 2];
  iov += 8;
  if (stream.fd === 1 || stream.fd === 2) {
   for (var j = 0; j < len; j++) {
    printChar(stream.fd, GROWABLE_HEAP_U8()[ptr+j]);
   }
   printChar(stream.fd, 0); // Allows printing non single lines
   ret += len;
  } else {
   var curr = FS.write(stream, GROWABLE_HEAP_I8(), ptr, len, offset);
   if (curr < 0) return -1;
   ret += curr;
  }
 }
 return ret;
}
"""


def replace_func(input: str, func_name: str, new_func: str) -> str:
    # Find position of function
    match = re.search(f"function {func_name}\\(.*?\\).*?{{", input, re.MULTILINE)
    if match == None:
        return input
    start = match.start()

    # Go forward find { and then }
    pos = match.end()
    brace_count = 1
    while pos < len(input) and brace_count > 0:
        pos += 1
        char = input[pos]
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1

    if pos >= len(input):
        raise Exception(f"Went off the end of the input str: {pos}")

    # See if there's a PTHREAD send to main thread. We have to copy this if so.
    # Emscripten uses this to handle all memory on the main thread
    function = input[start : pos + 1]
    pthread_match = re.search(
        "(if\\s*\\(ENVIRONMENT_IS_PTHREAD\\)\\s*return\\s*_emscripten_proxy_to_main_thread_js\\(.*?\\);)",
        function,
        re.MULTILINE,
    )
    if pthread_match is not None:
        # Insert position is after the first {
        insert_pos = new_func.find("{\n")
        if insert_pos >= 0:
            insert_pos += 2
            new_func = (
                new_func[:insert_pos]
                + pthread_match.group(0)
                + "\n"
                + new_func[insert_pos:]
            )

    # From start to pos should be the contents of the function
    return input[:start] + new_func + input[pos + 1 :]


def patch(input: str, output_dir: str):
    input = os.path.realpath(input)
    output_dir = os.path.realpath(output_dir)

    # Make sure not the same subdirectory (as we'll be copying a bunch of other files too)
    input_dir = os.path.dirname(input)
    if input_dir == output_dir:
        raise Exception(f"{input} dir is the same as the output.")

    if not os.path.exists(output_dir):
        raise Exception(f"{output_dir} has to exist prior to patching")

    # Remove the output tree and recreated it
    shutil.rmtree(output_dir, ignore_errors=True)
    os.mkdir(output_dir)

    # Create a build dir. This is where all the build output will go
    output_python_build_dir = os.path.realpath(
        os.path.join(output_dir, "build", "patched")
    )
    shutil.copytree(input_dir, output_python_build_dir)

    # This should already contain a python.js. That's the file we want to edit
    input_basename = os.path.basename(input)
    output_python_js = os.path.join(output_python_build_dir, input_basename)

    # Search for OS.py in the 'lib' folder. Need lib folder too
    os_py = os.path.realpath(os.path.join(input_dir, "..", "..", "Lib", "os.py"))
    if os.path.exists(os_py):
        shutil.copytree(os.path.dirname(os_py), os.path.join(output_dir, "Lib"))

    input_contents = None
    with open(input, "r") as f:
        input_contents = f.read()

    # Search for the different functions
    output_contents = replace_func(input_contents, "___syscall_bind", syscall_bind)
    output_contents = replace_func(
        output_contents, "___syscall_accept4", syscall_accept4
    )
    output_contents = replace_func(output_contents, "___syscall_socket", syscall_socket)
    output_contents = replace_func(output_contents, "___syscall_listen", syscall_listen)
    output_contents = replace_func(
        output_contents, "___syscall_connect", syscall_connect
    )
    output_contents = replace_func(
        output_contents, "___syscall_getsockname", syscall_getsockname
    )
    output_contents = replace_func(
        output_contents, "___syscall_recvfrom", syscall_recvfrom
    )
    output_contents = replace_func(output_contents, "doWritev", doWritev)

    # Stick in the prerun hook before the last 'run' entry
    length = len(output_contents)
    pos = length - 6
    while pos != length - 500 and not output_contents[pos:].startswith("run();"):
        pos -= 1

    if pos == length - 500:
        raise Exception(f"{input} seems to be missing a 'run();' call")

    output_contents = output_contents[:pos] + pre_run_code + output_contents[pos:]

    # Write these lines to the output
    with open(output_python_js, "w+") as f:
        f.write(output_contents)


parser = argparse.ArgumentParser(
    "patcher.py",
    description="Modifies the CPython's python.js to create custom sockets",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("--pythonjs", help="Path to the python.js file", required=True)
parser.add_argument(
    "--outputdir", help="Path to the massaged output dir", required=True
)


def main():
    args = parser.parse_args()
    patch(args.pythonjs, args.outputdir)


if __name__ == "__main__":
    main()
