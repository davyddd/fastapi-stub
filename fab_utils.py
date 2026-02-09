import hashlib


def _get_envs_from_file(file_path):
    envs = {}

    try:
        with open(file_path, 'r') as env_file:
            for line in env_file:
                if line.strip().startswith('#') or line.find('=') == -1:
                    continue

                name, value = line.split('=')[-2::]
                envs[name] = value
    except FileNotFoundError:
        pass

    return envs


def get_file_hash(file_path):
    return hashlib.md5(open(file_path, 'rb').read()).hexdigest()


def update_service_env_file(base_image_tag, **kwargs):
    old_envs = _get_envs_from_file('.env')

    envs = {
        **kwargs,
        'BASE_IMAGE_TAG': base_image_tag,
        'DEVELOP_DEPENDENCIES': old_envs.get('DEVELOP_DEPENDENCIES', '1')
    }

    with open('.env', 'w') as env_file:
        for name, value in envs.items():
            env_file.write(f'{name}={value}\n')
