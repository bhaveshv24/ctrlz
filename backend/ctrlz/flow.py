from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel


class RecoveryState(BaseModel):
    incident_id: str = ""


class RecoveryFlow(Flow[RecoveryState]):
    def __init__(self, engine, incident_id):
        super().__init__()
        self.engine = engine
        self.state.incident_id = incident_id

    @start()
    async def diagnose(self):
        return await self.engine.diagnose(self.state.incident_id)

    @listen(diagnose)
    async def plan(self, diagnosis):
        return await self.engine.plan(self.state.incident_id, diagnosis)

    @listen(plan)
    async def recover(self, proposal):
        return await self.engine.evaluate_execute(self.state.incident_id, proposal)
