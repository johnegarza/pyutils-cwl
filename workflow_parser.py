import subprocess, sys, fileinput, re
#import pdb

class WorkflowObject:
    def __init__(self, path):
        self.path = path
        self.upstream = []
        self.downstream = []
        self.docker_image = None

def path_resolver(parent_path, downstream_relative_path): 
    parsed_parent = parent_path.split("/")
    parsed_downstream = downstream_relative_path.split("/")
    directory_level = 1

    for dir in parsed_downstream:
        if dir == "..":
            directory_level += 1
        else:
            break
    
    parent_trim_num = len(parsed_parent) - directory_level
    trimmed_parent = parsed_parent[:parent_trim_num]

    trimmed_downstream = parsed_downstream[(directory_level-1):]

    path_list = trimmed_parent + trimmed_downstream
    return "/".join(path_list)

def print_hierarchy(cwl):
    print(cwl.path)
    print_hierarchy_kernel(cwl, 0, 1)

def print_hierarchy_kernel(cwl, index, depth):

    if index >= len(cwl.downstream):
        return

    path = "\t" * depth + cwl.downstream[index].path
    if cwl.downstream[index].docker_image is not None:
        path += "\t" + cwl.downstream[index].docker_image
    print(path)

    print_hierarchy_kernel(cwl.downstream[index], 0, depth + 1)
    print_hierarchy_kernel(cwl, index + 1, depth)

def docker_updater(old_image, new_image):

    #docker_files = [cwl.path for cwl in path_to_object.values() if cwl.docker_image == old_image]

    docker_files = [] #hold paths to the files that will have their docker images updated
    for cwl in path_to_object.values():
        if cwl.docker_image == old_image:
            cwl.docker_image = new_image #update the image in internal representation
            docker_files.append(cwl.path) 

    if not docker_files:
        pass
        #TODO implement some sort of warning or error handling- no matching files were found


    #adapted from https://stackoverflow.com/questions/125703/how-to-modify-a-text-file
    #and https://stackoverflow.com/questions/17140886/how-to-search-and-replace-text-in-a-file-using-python/20593644#20593644
    for line in fileinput.FileInput(docker_files, inplace = True):
        #used write instead of print to avoid adding in newline without using a version specific workaround
        sys.stdout.write(line.replace(old_image, new_image))

def propogate_argument(cwl_path, arg_name):

    ###############
    ### CAPTURE ###
    ###############

    arg_name += ":"

    argument = []
    leading_spaces = 0
    found_arg = False

    #grab the argument definition from the tool file
    with open(cwl_path) as contents:
        for num, line in enumerate(contents.readlines()):
            #print line.strip() + "\t" + arg_name
            if line.strip() == arg_name and not found_arg: #TODO evaluate necessity of !found_arg
                argument.append(line)
                leading_spaces = line.rstrip().count(' ')
                found_arg = True
            elif found_arg:
                #at this point, we've already found and are capturing the lines describing the desired argument
                #if we find a word at the same indentation level, it must be another arg, so stop capture
                if re.match("[\w]+:", line[leading_spaces:]) is not None: 
                    break
                else:
                    argument.append(line)

    if not argument:
        pass
        #TODO implement some sort of warning or error handling- argument was not found

    #print ''.join(argument)

    filtering = False
    filtered_argument = []
    for line in argument:
        if line.strip() == "inputBinding:" and not filtering:
            leading_spaces = line.rstrip().count(' ')
            filtering = True
            continue

        if filtering:
            if re.match("[\w]+:", line[leading_spaces:]) is not None:
                filtering = False
        if not filtering:
            filtered_argument.append(line)

    #print("filtered")
    #print ''.join(filtered_argument)

    #################
    ### PROPOGATE ###
    #################

    cwl = path_to_object[cwl_path]
    dups = set()
    dups.add(cwl)


    #TODO control flow and logic is spaghetti but I have a deadline- fix ASAP
    def walk(cwl_file, index, dups):

        arg_search = False #track if we've entered the section where we should be searching (input section)
        found_arg = False #track if we've found the argument in the file already, which must be overwritten
        leading_spaces = 0
        arg_string = ''.join(filtered_argument)
        if cwl_file not in dups:
            for line in fileinput.FileInput(cwl_file.path, inplace=True):
            
                if line.strip() == "inputs:":
                    sys.stdout.write(line)
                    #sys.stdout.write(arg_string)
                    arg_search = True
                elif arg_search: #we're in the inputs section
                    if line.strip() == arg_name:
                        found_arg = True
                        leading_spaces = line.rstrip().count(' ')
                        #no explicit write because we want to remove these lines, to be replaced later with the newer version
                    elif found_arg: #actively overwriting outdated argument
                        if re.match("[\w]+:", line[leading_spaces:]) is not None:
                            #in this case, we have found the next argument-
                            #so dump the new/updated argument, then update flags to skip this block next time
                            sys.stdout.write(arg_string)
                            sys.stdout.write(line)
                            arg_search = found_arg = False
                        #else, do nothing- with no explicit write, this deletes the old/outdated argument
                    elif line == line.lstrip(): #this will match top level lines
                        #in this case, we are leaving the inputs section but haven't written out the new argument
                        sys.stdout.write(arg_string)
                        sys.stdout.write(line)
                        arg_search = found_arg = False
                    else:
                        sys.stdout.write(line)
                else:
                    #necessary because the above line.strip() check
                    #removes the line from the file
                    sys.stdout.write(line)

            dups.add(cwl_file)

        if index >= len(cwl_file.upstream):
            return

        walk(cwl_file.upstream[index], 0, dups)
        walk(cwl_file, index + 1, dups)

    walk(cwl, 0, dups)

def upstreams(cwl_file, index, dups):
    if cwl_file not in dups:
        print(cwl_file.path)
        dups.add(cwl_file)
    if index >= len(cwl_file.upstream):
        return
    upstreams(cwl_file.upstream[index], 0, dups)
    upstreams(cwl_file, index + 1, dups)

#TODO wrap the following portion in if __name-- == "__main__"
#refactor and check scope on all variables when apply this update

cwls = subprocess.check_output(['find', '.', '-name', '*\.cwl']).split("\n") #create a list of paths to all cwl files
del cwls[-1] #last element is always the empty string, so remove it

path_to_object = dict()
for cwl in cwls:
    path_to_object[cwl] = WorkflowObject(cwl)

for cwl in cwls:
    input_mapping_capture = False
    with open(cwl) as contents:
        lines = contents.readlines() #create a list of lines in the cwl file
        lines = [x.strip() for x in lines] #remove whitespace from the beginning and end of each line
        for line in lines:
            if line.startswith("run: "):
                downstream_path = path_resolver(cwl, line[5:])

                parent_obj = path_to_object[cwl]
                downstream_obj = path_to_object[downstream_path]

                parent_obj.downstream.append(downstream_obj)
                downstream_obj.upstream.append(parent_obj)

                input_mapping_capture = True

            elif line.startswith("dockerPull: "):
                image = line[12:].strip("\"")
                cwl_obj = path_to_object[cwl]
                cwl_obj.docker_image = image
            elif input_mapping_capture:
                if line.startswith("in:"):
                    continue #nothing to do here
                elif line.startswith("out:"):
                    input_mapping_capture = False
                else:
                    pass #TODO implement parsing

#docker_updater("mgibio/samtools-cwl:1.0.0", "testing")
print_hierarchy(path_to_object["./definitions/pipelines/exome.cwl"])
#propogate_argument("./unaligned_bam_to_bqsr/align_and_tag.cwl", "tester")

'''
top_levels = set()

for cwl in path_to_object.values():
    if not cwl.upstream:
        top_levels.add(cwl)

for thing in top_levels:
    print_hierarchy(thing)
'''

'''
dups = set()
trans_file = path_to_object[sys.argv[1]]
upstreams(trans_file, 0, dups)
'''
