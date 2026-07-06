import logging

logger = logging.getLogger('judge.checker')


class Checker:
    @staticmethod
    def check(user_out_path: str, ans_out_path: str) -> bool:
        try:
            with open(user_out_path, 'r', encoding='utf-8') as f1, \
                 open(ans_out_path, 'r', encoding='utf-8') as f2:
                user = [l.rstrip() for l in f1.readlines() if l.strip()]
                ans  = [l.rstrip() for l in f2.readlines() if l.strip()]
            return user == ans
        except FileNotFoundError:
            logger.warning('Checker: output file missing — user=%s, ans=%s',
                           user_out_path, ans_out_path)
            return False
        except Exception:
            logger.exception('Checker: unexpected error')
            return False
