import logging

from dramatiq import Retry
from dramatiq.middleware import Middleware

logger = logging.getLogger(__name__)


class TaskLoggingMiddleware(Middleware):
    @staticmethod
    def merge_arg_names_values(fn, args, kwargs):
        params = {
            **{
                attribute_name: args[item]
                for item, attribute_name in enumerate(tuple(fn.__annotations__.keys())[: len(args)], start=0)
            },
            **kwargs,
        }
        return params

    @staticmethod
    def filter_params(params: dict):
        for key in list(params.keys()):
            if isinstance(params.get(key), (list, tuple, set, dict)):
                params.pop(key)

    def get_filtered_params(self, broker, message):
        try:
            actor = broker.get_actor(message.actor_name)
            params = self.merge_arg_names_values(actor.fn, message.args, message.kwargs)
            self.filter_params(params)
            return params
        except Exception as e:  # noqa: BLE001
            logger.error(
                {'message': 'Getting params in dramatiq message failed', 'broker_message': str(message), 'error': str(e)}
            )
            return {}

    def before_process_message(self, broker, message):
        params = self.get_filtered_params(broker, message)

        logger.info({'message': f'Started task {message.actor_name}', **params})

    def after_process_message(self, broker, message, *, result=None, exception=None):
        params = self.get_filtered_params(broker, message)

        if exception is None:
            logger.info(
                {
                    'message': f'Finished task {message.actor_name}',
                    **({'result': result} if result is not None else {}),
                    **params,
                }
            )
        elif not isinstance(exception, Retry):
            logger.info({'message': f'Failed task {message.actor_name}', **params})
