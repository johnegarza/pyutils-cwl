import subprocess

class WorkflowObject:
    def __init__(self, path):
        self.path = path
        self.upstream = []
        self.downstream = []

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

    tabs = "\t" * depth
    print(tabs + cwl.downstream[index].path)

    print_hierarchy_kernel(cwl.downstream[index], 0, depth+1)
    print_hierarchy_kernel(cwl, index+1, depth)

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

'''
print("Top level workflows:")
for cwl in path_to_object:
    obj = path_to_object[cwl]
    if len(obj.upstream) == 0:
        print(obj.path)
'''

print_hierarchy(path_to_object["./exome_workflow.cwl"])




