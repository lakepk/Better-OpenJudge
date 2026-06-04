class Checker:
    @staticmethod
    def check(user_out_path:str,ans_out_path:str)->bool:
        """
        标准文本比对逻辑（严格比对，忽略行末空格和文末换行）
        """
        try:
            with open(user_out_path,'r',encoding='utf-8') as f1,\
                 open(ans_out_path,'r',encoding='utf-8') as f2:
                
                # 过滤掉纯空行，并去掉每行末尾的空白字符
                user_lines=[line.rstrip() for line in f1.readlines() if line.strip()]
                ans_lines=[line.rstrip() for line in f2.readlines() if line.strip()]
                
            return user_lines==ans_lines
        except Exception:
            return False