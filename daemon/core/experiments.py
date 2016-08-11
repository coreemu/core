#
# CORE
# Copyright (c)2016 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Rod Santiago
#


from core.api import core_pb2
from multiprocessing import Lock




class ExperimentStore(object):
    __lastid = 0
    __experiments = {}
    __lock = Lock()

    @staticmethod
    def addExperiment(exp):
        with ExperimentStore.__lock:
            id = str(ExperimentStore.__lastid)
            ExperimentStore.__lastid += 1
            exp.experimentId = id
            if not id in ExperimentStore.__experiments:
                ExperimentStore.__experiments[id] = exp
                return True
            else:
                return False
            

    @staticmethod
    def delExperiment(exp):
        if not exp.HasField("experimentId"):
            print 'Experiment ID is needed but not supplied'
            return False
        id = exp.experimentId
        with ExperimentStore.__lock:
            if id in ExperimentStore.__experiments:
                del ExperimentStore.__experiments[id]
                return True
            else:
                return False


        

