#****************************************************************************
#* task_memento.py
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
import pydantic.dataclasses as dc
from pydantic import BaseModel
from typing import Any, Dict, List

class TaskMemento(BaseModel):
    dep_ids : List[int] = dc.Field(default_factory=list)
    params : Dict[str,Any] = dc.Field(default_factory=dict)

    def clone(self) -> 'TaskMemento':
        ret = TaskMemento()
        ret.params = self.params.copy()
        ret.dep_ids = self.dep_ids.copy()
        return ret



