from datetime import datetime, timedelta


def notice_format_time(time):
    now = datetime.now()
    time_elapsed = now - time
    if time_elapsed < timedelta(minutes=1):
        return "방금"
    elif time_elapsed < timedelta(hours=1):
        return f"{int(time_elapsed.seconds / 60)}분"
    elif time_elapsed < timedelta(days=1):
        return f"{int(time_elapsed.seconds / (60 * 60))}시간"
    elif time_elapsed < timedelta(days=7):
        return f"{time_elapsed.days}일"
    else:
        if time_elapsed.days > 60:
            return False
        week = time_elapsed.days // 7
        return f"{week}주"
