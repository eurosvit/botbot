import json, logging, sys
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload={"level":record.levelname,"msg":record.getMessage(),"logger":record.name,
                 "time":self.formatTime(record,datefmt="%Y-%m-%dT%H:%M:%S%z")}
        if record.exc_info: payload["exc_info"]=self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
def configure_logging():
    h=logging.StreamHandler(sys.stdout); h.setFormatter(JsonFormatter())
    root=logging.getLogger(); root.setLevel(logging.INFO); root.handlers=[h]
