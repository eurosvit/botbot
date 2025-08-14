
import json, logging, sys
class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"level":record.levelname,"msg":record.getMessage(),"logger":record.name,
                           "time":self.formatTime(record,"%Y-%m-%dT%H:%M:%S%z")}, ensure_ascii=False)
def configure_logging():
    h=logging.StreamHandler(sys.stdout); h.setFormatter(JsonFormatter())
    root=logging.getLogger(); root.setLevel(logging.INFO); root.handlers=[h]
