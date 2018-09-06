import subprocess, sys, fileinput
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

    #adapted from https://stackoverflow.com/questions/125703/how-to-modify-a-text-file
    #and https://stackoverflow.com/questions/17140886/how-to-search-and-replace-text-in-a-file-using-python/20593644#20593644
    for line in fileinput.FileInput(docker_files, inplace = True):
        #used write instead of print to avoid adding in newline without using a version specific workaround
        sys.stdout.write(line.replace(old_image, new_image))

cwls = subprocess.check_output(['find', '.', '-name', '*\.cwl']).split("\n") #create a list of paths to all cwl files
del cwls[-1] #last element is always the empty string, so remove it

path_to_object = dict()
for cwl in cwls:
    path_to_object[cwl] = WorkflowObject(cwl)

for cwl in cwls:
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

            elif line.startswith("dockerPull: "):
                image = line[12:].strip("\"")
                cwl_obj = path_to_object[cwl]
                cwl_obj.docker_image = image

docker_updater("mgibio/samtools-cwl:1.0.0", "testing")
print_hierarchy(path_to_object["./exome_workflow.cwl"])




