import os


def get_int_env_var(key: str,defautl: int) -> int:
    val = os.getenv(key,str(defautl))
    try:
        return int(val)
    except ValueError:
        return defautl

MAX_REPLICA_DELAY_SECONDS = get_int_env_var("MAX_REPLICA_DELAY_SECONDS",60)