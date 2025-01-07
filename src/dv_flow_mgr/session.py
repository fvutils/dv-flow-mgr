#****************************************************************************
#* session.py
#*
#* Copyright 2023 Matthew Ballance and Contributors
#*
#* Licensed under the Apache License, Version 2.0 (the "License"); you may 
#* not use this file except in compliance with the License.  
#* You may obtain a copy of the License at:
#*
#*   http://www.apache.org/licenses/LICENSE-2.0
#*
#* Unless required by applicable law or agreed to in writing, software 
#* distributed under the License is distributed on an "AS IS" BASIS, 
#* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
#* See the License for the specific language governing permissions and 
#* limitations under the License.
#*
#* Created on:
#*     Author: 
#*
#****************************************************************************
import os
import yaml
import dataclasses as dc
from typing import Any, Dict, List
from .package import Package
from .package_def import PackageDef, PackageSpec
from .task import Task,TaskSpec

@dc.dataclass
class Session(object):
    """Manages the running of a flow"""

    srcdir : str
    rundir : str

    # Search path for .dfs files
    package_path : List[str] = dc.field(default_factory=list)
    package : PackageDef = None
    _root_dir : str = None
    _pkg_s : List[Package] = dc.field(default_factory=list)
    _pkg_m : Dict[PackageSpec,Package] = dc.field(default_factory=dict)
    _pkg_spec_s : List[PackageDef] = dc.field(default_factory=list)
    _pkg_def_m : Dict[str,PackageDef] = dc.field(default_factory=dict)
    _task_list : List[Task] = dc.field(default_factory=list)
    _task_m : Dict[TaskSpec,Task] = dc.field(default_factory=dict)
    _task_id : int = 0
    _rundir_s : List[str] = dc.field(default_factory=list)

    def __post_init__(self):
        from .tasklib.std.pkg_std import PackageStd
        from .tasklib.hdl.sim.vlt_pkg import VltPackage
        self._pkg_m[PackageSpec("std")] = PackageStd("std")
        self._pkg_m[PackageSpec("hdl.sim.vlt")] = VltPackage("hdl.sim.vlt")

    def load(self, root : str):
        if not os.path.isdir(root):
            raise Exception("Root directory %s does not exist" % root)

        if not os.path.isfile(os.path.join(root, "flow.yaml")):
            raise Exception("No root flow file")

        self._root_dir = os.path.dirname(root)
        self.package = self._load_package(os.path.join(root, "flow.yaml"), [])

        return self.package

    def mkTaskGraph(self, task : str) -> Task:
        self._pkg_s.clear()
        self._task_m.clear()

        self._rundir_s.clear()
        self._rundir_s.append(self.rundir)

        return self._mkTaskGraph(task)
        
    def _mkTaskGraph(self, task : str, params : dict = None) -> Task:

        elems = task.split(".")

        pkg_name = ".".join(elems[0:-1])
        task_name = elems[-1]

        self._rundir_s.append(os.path.join(self._rundir_s[-1], pkg_name, task_name))

        if pkg_name == "":
            if len(self._pkg_spec_s) == 0:
                raise Exception("No package context for %s" % task)
            pkg_spec = self._pkg_spec_s[-1]
        else:
            pkg_spec = PackageSpec(pkg_name)
            self._pkg_spec_s.append(pkg_spec)
        pkg = self.getPackage(pkg_spec)
        
        self._pkg_s.append(pkg)

        #task_def = pkg.getTask(task_name)

        depends = []

        params = pkg.mkTaskParams(task_name)

        task_id = self.mkTaskId(None)
#        task_name = "%s.%s" % (pkg.name, task_def.name)

        # The returned task should have all param references resolved
        task = pkg.mkTask(
            task_name,
            task_id,
            self,
            params,
            depends)
        task.rundir = self._rundir_s[-1]
        
        for i,d in enumerate(task.depend_refs):
            if d in self._task_m.keys():
                task.depends[i] = self._task_m[d]
            else:
                task.depends[i] = self._mkTaskGraph(d)

        self._task_m[task.name] = task

        self._pkg_s.pop()
        self._pkg_spec_s.pop()
        self._rundir_s.pop()

        return task
    
    def mkTaskId(self, task : 'Task') -> int:
        self._task_id += 1
        # TODO: save task <-> id map for later?
        return self._task_id

    async def run(self, task : str) -> 'TaskData':
        impl = self.mkTaskGraph(task)
        return await impl.do_run()

    def _load_package(self, root : str, file_s : List[str]) -> PackageDef:
        if root in file_s:
            raise Exception("Recursive file processing @ %s: %s" % (root, ",".join(self._file_s)))
        file_s.append(root)
        ret = None
        with open(root, "r") as fp:
            doc = yaml.load(fp, Loader=yaml.FullLoader)
            if "package" not in doc.keys():
                raise Exception("Missing 'package' key in %s" % root)
            pkg = PackageDef(**(doc["package"]))
            pkg.basedir = os.path.dirname(root)

#            for t in pkg.tasks:
#                t.basedir = os.path.dirname(root)

        if not len(self._pkg_spec_s):
            self._pkg_spec_s.append(PackageSpec(pkg.name))
            self._pkg_def_m[PackageSpec(pkg.name)] = pkg
        else:
            if self._pkg_spec_s[0].name != pkg.name:
                raise Exception("Package name mismatch: %s != %s" % (self._pkg_m[0].name, pkg.name))
            else:
                # TODO: merge content
                self._pkg_spec_s.append(PackageSpec(pkg.name))

        print("pkg: %s" % str(pkg))
        
        # TODO: read in fragments

        self._pkg_spec_s.pop()
        file_s.pop()

        return pkg

    def getPackage(self, spec : PackageSpec) -> Package:
        pkg_spec = self._pkg_spec_s[-1]
        pkg_def = self._pkg_def_m[pkg_spec]

        # Need a stack to track which package we are currently in
        # Need a map to get a concrete package from a name with parameterization

        # Note: _pkg_m needs to be context specific, such that imports from
        # one package don't end up visible in another
        if spec in self._pkg_m.keys():
            pkg = self._pkg_m[spec]
        elif spec in self._pkg_def_m.keys():
            pkg = self._pkg_def_m[spec].mkPackage(self)
            self._pkg_m[spec] = pkg
        else:
            pkg = None
            print("imports: %s" % str(pkg_def.imports))
            for imp in pkg_def.imports:
                print("imp: %s" % str(imp))
                if imp.alias is not None and imp.alias == spec.name:
                    # Found the alias name. Just need to get an instance of this package
                    tgt_pkg_spec = PackageSpec(imp.name)
                    if tgt_pkg_spec in self._pkg_m.keys():
                        pkg = self._pkg_m[tgt_pkg_spec]
                    elif tgt_pkg_spec in self._pkg_def_m.keys():
                        base = self._pkg_def_m[tgt_pkg_spec]
                        pkg = base.mkPackage(self, spec.params)
                        self._pkg_m[spec] = pkg
                    elif imp.path is not None:
                        # See if we can load the package
                        print("TODO: load referenced package")
                    else:
                        raise Exception("Import alias %s not found" % imp.name)
                    break
                else:
                    # Need to compare the spec with the full import spec
                    imp_spec = PackageSpec(imp.name)
                    # TODO: set parameters
                    if imp_spec == spec:
                        base = self._pkg_def_m[PackageSpec(spec.name)]
                        pkg = base.mkPackage(self, spec.params)
                        self._pkg_m[spec] = pkg
                        break

            if pkg is None:
                raise Exception("Failed to find package %s from package %s" % (
                    spec.name, pkg_def.name))

#            base_spec = PackageSpec(spec.name)
#            if not base_spec in self._pkg_def_m.keys():
#                # Template is not present. Go find it...
#
#                # If not found...
#                raise Exception("Package %s not found" % spec.name)

        return pkg
        
    def getTaskCtor(self, spec : TaskSpec, pkg : PackageDef) -> 'TaskCtor':
        spec_e = spec.name.split(".")
        task_name = spec_e[-1]
        pkg_name = ".".join(spec_e[0:-1])

        try:
            pkg = self.getPackage(PackageSpec(pkg_name))
        except Exception as e:
            print("Failed to find package %s while looking for task %s" % (pkg_name, spec.name))
            raise e

        return pkg.getTaskCtor(task_name)

