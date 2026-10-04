from pythonjsonlogger.json import JsonFormatter

from dddesign.utils.base_model import flatten_model_dump

from config.logging.log_properties import log_properties_registry


class CustomJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        try:
            log_properties = log_properties_registry.get()
        except RuntimeError:
            # outside of an execution scope (startup, scheduler): nothing to add
            return

        if log_properties:
            for key, value in flatten_model_dump(log_properties, mode='json', exclude_none=True).items():
                log_record.setdefault(key, value)
