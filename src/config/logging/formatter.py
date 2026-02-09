from pythonjsonlogger.json import JsonFormatter


class CustomJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        name = log_record.get('name')
        if name == 'uvicorn.access' and isinstance(record.args, tuple):
            ip_address, method, url_path, http_version, status_code = record.args  # noqa: F841
            log_record['message'] = f'RESPONSE {method} {url_path}'

            log_record.update(method=method, url_path=url_path, ip_address=ip_address, status_code=status_code)
