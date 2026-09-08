from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
try:
    from openai import OpenAI
except (ImportError, AttributeError):  # rule-only mode still works without the SDK
    OpenAI = None  # type: ignore
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "autofill.db"
SEED_PATH = DATA_DIR / "profile_seed.json"
SEED_VERSION = "family-profile-20260908-v5"
ENV_PATH = ROOT / ".env"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_dotenv_robust(path: Path) -> str:
    """Load .env files saved by common Windows editors without crashing startup.

    UTF-8 is preferred, but legacy Windows/Chinese editors may save the file as
    GBK/GB18030 or UTF-16. We retry those encodings and keep rule-only mode
    available even if the file is malformed.
    """
    if not path.exists():
        return "missing"
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936", "utf-16", "cp1252"):
        try:
            load_dotenv(path, encoding=encoding, override=False)
            return encoding
        except (UnicodeDecodeError, UnicodeError) as exc:
            last_error = exc
        except Exception as exc:
            # Parsing errors should not make the whole local service unusable.
            last_error = exc
            break
    print(f"Warning: could not read {path.name}; starting without it: {last_error}")
    return "unreadable"


ENV_ENCODING = load_dotenv_robust(ENV_PATH)

DEFAULT_PROFILE: Dict[str, Any] = {
    "basic": {
        "name_cn": "",
        "name_en": "",
        "id_type": "",
        "id_number": "",
        "phone_country_code": "",
        "phone": "",
        "email": "",
        "gender": "",
        "birthday": "",
        "political_status": "",
        "ethnicity": "",
        "height_cm": "",
        "weight_kg": "",
        "hometown": "",
        "student_origin": "",
        "current_city": "",
        "current_address": "",
        "marital_status": "",
        "health_status": "",
        "pre_enrollment_household_location": "",
        "mailing_address": "",
        "postal_code": "",
    },
    "education": [
        {
            "school": "",
            "degree": "",
            "academic_degree": "",
            "college": "",
            "major": "",
            "research_direction": "",
            "courses": "",
            "start_date": "",
            "end_date": "",
            "first_degree": "",
            "full_time": "",
            "exchange_program": "",
            "gpa": "",
            "ranking": "",
            "education_type": "",
            "study_length_years": "",
            "overseas_study_experience": "",
            "graduation_project": "",
        }
    ],
    "internships": [],
    "campus_experience": {
        "is_student_cadre": "",
        "start_date": "",
        "end_date": "",
        "description": "",
    },
    "student_activities": [],
    "skills": {
        "cet4": "",
        "cet6": "",
        "tem4": "",
        "tem8": "",
        "other_language": "",
        "computer_level": "",
        "certificates": "",
    },
    "awards": [],
    "family": {
        "has_relative_in_cmb_group": "",
        "members": [],
        "emergency_contact": {"name": "", "employer": "", "position": "", "phone": ""},
    },
    "personality": {"words": []},
    "photos": {"formal_photo": "", "life_photo": ""},
    "job_preferences": {
        "cities": [],
        "job_types": [],
        "salary": "",
        "accept_location_transfer": "",
    },
    "summaries": {
        "education_text": "",
        "internships_text": "",
        "student_activities_text": "",
        "awards_text": "",
        "skills_text": "",
        "personality_text": "",
    },
    "source": {},
}

# Only keys listed here are eligible for automatic field matching.  Arrays are
# intentionally conservative: we expose specific positions only when the label
# says which record is being requested.  This avoids filling every repeated
# "单位名称" field with the first internship.
FIELD_DEFS: Dict[str, List[str]] = {
    "basic.name_cn": ["姓名", "中文姓名", "真实姓名", "应聘者姓名", "申请人姓名", "name", "full name"],
    "basic.name_en": ["英文名", "英文姓名", "english name", "name in english"],
    "basic.id_type": ["证件号码类型", "证件类型", "身份证件类型", "identity document type", "id type"],
    "basic.id_number": ["证件号码", "身份证号码", "身份证号", "证件号", "identity number", "id number"],
    "basic.phone_country_code": ["手机区号", "手机国家区号", "电话国家区号", "country calling code"],
    "basic.phone": ["手机号", "手机号码", "联系电话", "电话", "mobile", "phone", "telephone"],
    "basic.email": ["邮箱", "电子邮箱", "电子邮件", "email", "e-mail"],
    "basic.gender": ["性别", "gender", "sex"],
    "basic.birthday": ["出生日期", "生日", "出生年月", "date of birth", "birthday", "dob"],
    "basic.political_status": ["政治面貌", "政治身份", "political status"],
    "basic.ethnicity": ["民族", "民族信息", "ethnicity"],
    "basic.height_cm": ["身高", "身高cm", "height"],
    "basic.weight_kg": ["体重", "体重kg", "weight"],
    "basic.hometown": ["籍贯", "祖籍", "native place", "hometown"],
    "basic.student_origin": ["生源地", "生源所在地", "生源地区", "student origin"],
    "basic.current_city": ["现居地", "现居城市", "当前城市", "current city", "city of residence"],
    "basic.current_address": ["现住址", "现居住址", "现居地址", "当前住址", "current address"],
    "basic.marital_status": ["婚姻情况", "婚姻状况", "marital status"],
    "basic.health_status": ["健康状况", "健康情况", "身体状况", "health status"],
    "basic.pre_enrollment_household_location": ["入学前户口所在地", "入学前户籍所在地", "入学前户口", "入学前户籍"],
    "basic.mailing_address": ["通讯地址", "通信地址", "邮寄地址", "联系地址", "mailing address", "postal address"],
    "basic.postal_code": ["邮政编码", "邮编", "邮递区号", "postal code", "zip code"],

    "education[0].school": ["毕业院校", "最高学历院校", "研究生院校", "硕士院校", "学校", "院校", "university", "school", "college"],
    "education[0].degree": ["学历", "最高学历", "研究生学历", "硕士学历", "education level"],
    "education[0].academic_degree": ["学位", "最高学位", "研究生学位", "硕士学位", "academic degree"],
    "education[0].college": ["研究生院系", "硕士院系", "最高学历院系", "院系", "学院"],
    "education[0].major": ["专业", "所学专业", "最高学历专业", "研究生专业", "硕士专业", "major", "field of study"],
    "education[0].research_direction": ["研究方向", "硕士研究方向", "研究生研究方向", "research direction", "research area"],
    "education[0].courses": ["专业课程", "主要课程", "研究生专业课程", "硕士专业课程", "major courses", "core courses"],
    "education[0].start_date": ["研究生入学时间", "硕士入学时间", "最高学历入学时间", "入学时间", "入学日期", "enrollment date"],
    "education[0].end_date": ["毕业时间", "预计毕业时间", "最高学历毕业时间", "研究生毕业时间", "graduation date"],
    "education[0].full_time": ["最高学历是否全日制", "研究生是否全日制", "是否全日制"],
    "education[0].exchange_program": ["最高学历合作交流项目", "研究生合作交流项目", "合作交流项目"],
    "education[0].gpa": ["gpa", "绩点", "平均绩点", "grade point average"],
    "education[0].ranking": ["研究生成绩排名", "最高学历成绩排名", "成绩排名", "专业排名", "ranking", "class rank"],
    "education[0].education_type": ["受教育类型", "教育类型", "研究生受教育类型", "硕士受教育类型"],
    "education[0].study_length_years": ["学制", "研究生学制", "硕士学制", "学制年限"],
    "education[0].overseas_study_experience": ["该段教育经历内是否有海外学习经历", "是否有海外学习经历", "海外学习经历", "海外经历"],
    "education[0].graduation_project": ["硕士毕业设计", "硕士毕业论文", "毕业设计", "毕业论文题目", "毕业课题"],

    "education[1].school": ["本科院校", "本科学校", "本科毕业院校", "本科就读学校", "undergraduate school", "bachelor university"],
    "education[1].degree": ["本科学历", "本科层次", "本科教育学历", "undergraduate education level"],
    "education[1].academic_degree": ["本科学位", "学士学位", "本科教育学位", "undergraduate degree", "bachelor degree"],
    "education[1].college": ["本科院系", "本科院系名称", "本科所在学院"],
    "education[1].major": ["本科专业", "本科所学专业", "undergraduate major"],
    "education[1].courses": ["本科专业课程", "本科主要课程", "本科课程", "undergraduate courses"],
    "education[1].start_date": ["本科入学时间", "本科开始时间"],
    "education[1].end_date": ["本科毕业时间", "本科结束时间"],
    "education[1].ranking": ["本科成绩排名", "本科专业排名"],
    "education[1].education_type": ["本科受教育类型", "本科教育类型"],
    "education[1].study_length_years": ["本科学制", "本科学制年限"],
    "education[1].overseas_study_experience": ["本科是否有海外学习经历", "本科海外学习经历"],
    "education[1].graduation_project": ["本科毕业设计", "本科毕业论文", "本科毕业课题"],

    "internships[0].company": ["最近实习单位", "最近一段实习单位", "第一段实习单位", "实习单位1", "最近实践单位"],
    "internships[0].city": ["最近实习城市", "第一段实习城市", "实习城市1"],
    "internships[0].role": ["最近实习岗位", "最近实习职位", "第一段实习岗位", "实习岗位1"],
    "internships[0].start_date": ["最近实习开始时间", "第一段实习开始时间", "实习开始时间1"],
    "internships[0].end_date": ["最近实习结束时间", "第一段实习结束时间", "实习结束时间1"],
    "internships[0].description": ["最近实习内容", "最近实践内容", "第一段实习内容", "实习内容1"],

    "skills.cet4": ["cet4", "cet-4", "英语四级", "大学英语四级", "四级成绩", "cet4成绩"],
    "skills.cet6": ["cet6", "cet-6", "英语六级", "大学英语六级", "六级成绩", "cet6成绩"],
    "skills.computer_level": ["计算机水平", "计算机能力", "computer skills"],
    "skills.certificates": ["技能证书", "资格证书", "证书情况", "certificates"],

    "family.members[0].name": ["父亲姓名", "父亲名字"],
    "family.members[0].age": ["父亲年龄"],
    "family.members[0].employer": ["父亲工作单位", "父亲单位"],
    "family.members[0].department": ["父亲工作部门", "父亲部门"],
    "family.members[0].position": ["父亲职位", "父亲职务"],
    "family.members[0].phone": ["父亲电话", "父亲联系电话"],
    "family.members[0].political_status": ["父亲政治面貌"],
    "family.members[0].is_china_post_employee": ["父亲是否为中国邮政系统职工", "父亲是否中国邮政系统职工"],
    "family.members[1].name": ["母亲姓名", "母亲名字"],
    "family.members[1].age": ["母亲年龄"],
    "family.members[1].employer": ["母亲工作单位", "母亲单位"],
    "family.members[1].department": ["母亲工作部门", "母亲部门"],
    "family.members[1].position": ["母亲职位", "母亲职务"],
    "family.members[1].phone": ["母亲电话", "母亲联系电话"],
    "family.members[1].political_status": ["母亲政治面貌"],
    "family.members[1].is_china_post_employee": ["母亲是否为中国邮政系统职工", "母亲是否中国邮政系统职工"],
    "family.emergency_contact.name": ["紧急联系人", "紧急联络人", "紧急联系人姓名"],
    "family.emergency_contact.employer": ["紧急联系人工作单位", "紧急联络人工作单位"],
    "family.emergency_contact.position": ["紧急联系人职位", "紧急联络人职务"],
    "family.emergency_contact.phone": ["紧急联系人电话", "紧急联络人电话", "紧急联系电话"],
    # This answer is source-company specific; do not generalize it to arbitrary employers.
    "family.has_relative_in_cmb_group": [
        "是否有近亲属在招商局集团工作",
        "是否有近亲属在招商银行工作",
        "是否有近亲属在招商局集团及其附属公司工作",
        "是否有近亲属在招商银行及其附属公司工作",
    ],

    "campus_experience.is_student_cadre": ["是否为学生干部", "校园经历是否为学生干部", "是否学生干部", "学生干部"],
    "campus_experience.start_date": ["校园经历开始时间", "学生干部开始时间", "校园活动开始时间", "开始时间"],
    "campus_experience.end_date": ["校园经历结束时间", "学生干部结束时间", "校园活动结束时间", "结束时间"],
    "campus_experience.description": ["校园经历主要内容", "校园经历内容", "学生干部经历", "校园活动主要内容", "校园经历描述"],

    "summaries.education_text": ["教育经历", "教育背景", "学习经历"],
    "summaries.internships_text": ["实习经历", "实习经验", "社会实践", "实践经历", "工作实践经历"],
    "summaries.student_activities_text": ["社团经历", "学生工作", "学生社团活动", "校园活动"],
    "summaries.awards_text": ["个人荣誉", "获奖情况", "奖项", "荣誉奖励", "荣誉奖项"],
    "summaries.skills_text": ["技能水平", "技能情况", "语言水平", "外语水平"],
    "summaries.personality_text": ["性格", "性格描述", "用五个词描述性格", "五个词语描述您的性格", "personality"],

    "job_preferences.cities": ["意向城市", "期望城市", "工作地点", "意向工作地点", "期望工作地点", "preferred city", "work location"],
    "job_preferences.job_types": ["意向岗位", "期望岗位", "职位类别", "求职方向", "desired role", "job type"],
    "job_preferences.salary": ["期望薪资", "期望年薪", "薪资期望", "expected salary", "salary expectation"],
    "job_preferences.accept_location_transfer": ["是否服从调剂", "是否接受调剂", "是否接受工作地点调剂", "服从工作地点调剂", "accept transfer"],
}



REPEATABLE_FIELD_DEFS: Dict[str, Dict[str, List[str]]] = {
    "internships": {
        "work_type": ["工作类型", "经历类型", "实习类型", "工作性质"],
        "company": ["工作单位", "单位名称", "公司名称", "实习单位", "实践单位"],
        "role": ["岗位", "职位", "职务", "工作岗位", "实习岗位"],
        "city": ["所在城市", "工作城市", "城市"],
        "start_date": ["入职时间", "开始时间", "起始时间", "开始日期", "实习开始时间"],
        "end_date": ["离职时间", "结束时间", "终止时间", "结束日期", "实习结束时间"],
        "description": ["主要工作职责和业绩", "工作职责和业绩", "主要工作职责", "工作职责", "工作内容", "实践内容", "主要职责", "工作业绩"],
        "salary": ["职位月薪税前", "职位月薪", "月薪税前", "月薪", "薪资", "税前月薪"],
        "contact_name": ["单位联系人", "联系人", "单位联系人员"],
        "contact_phone": ["单位联系电话", "联系人电话", "联系电话"],
    },
    "awards": {
        "date": ["获奖时间", "奖项时间", "时间", "日期"],
        "name": ["奖项名称", "获奖名称", "荣誉名称", "奖励名称"],
        "level": ["奖项级别", "获奖级别", "级别"],
        "type": ["奖项类型", "荣誉类型", "类型"],
        "reference": ["出版书号期刊名称专利号", "期刊名称", "专利号", "参考信息"],
        "details": ["详细说明", "获奖说明", "奖项说明", "备注"],
    },
    "family": {
        "relation": ["与本人关系", "与申请人关系", "亲属关系", "关系"],
        "name": ["亲属姓名", "家庭成员姓名", "成员姓名", "姓名"],
        "age": ["年龄"],
        "employer": ["工作单位", "所在单位", "单位名称", "工作机构"],
        "department": ["工作部门", "所在部门", "部门"],
        "position": ["职务", "职位", "岗位"],
        "phone": ["联系电话", "手机号码", "手机号", "电话"],
        "political_status": ["政治面貌", "政治身份"],
        "is_china_post_employee": ["是否为中国邮政系统职工", "是否中国邮政系统职工", "中国邮政系统职工"],
    },
}

REPEATABLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    # Do not force a site-specific work-type value. Some ATSes use this field for
    # the functional category (for example "软件开发") rather than "实习".
    "internships": {},
    "awards": {},
    "family": {},
}

OPTION_ALIASES = {
    "身份证": ["身份证", "居民身份证", "中华人民共和国居民身份证"],
    "健康": ["健康", "良好", "身体健康"],
    "全日制教育": ["全日制教育", "全日制", "普通全日制"],
    "无": ["无", "没有", "否", "none", "no"],
    "其他": ["其他", "其它", "other"],
    "男": ["男", "男性", "male", "m"],
    "女": ["女", "女性", "female", "f"],
    "本科": ["本科", "大学本科", "学士", "bachelor", "undergraduate"],
    "硕士研究生": ["硕士", "硕士研究生", "研究生", "master", "masters", "master's"],
    "博士研究生": ["博士", "博士研究生", "phd", "doctor", "doctoral"],
    "中国共产主义青年团团员": ["中国共产主义青年团团员", "共青团员", "团员"],
    "未婚": ["未婚", "未婚人士", "single"],
    "已婚": ["已婚", "married"],
    "是": ["是", "愿意", "接受", "可以", "yes", "y"],
    "否": ["否", "不愿意", "不接受", "不可以", "no", "n"],
    "前20%": ["前20%", "前20％", "20%", "前百分之二十"],
    "中等": ["中等", "中游", "中等水平"],
}


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_seed_profile() -> Optional[Dict[str, Any]]:
    if not SEED_PATH.exists():
        return None
    try:
        data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as exc:
        print(f"Profile seed load failed: {exc}")
        return None


def schema_merge(default: Any, current: Any) -> Any:
    """Add newly introduced schema fields without overwriting current values."""
    if isinstance(default, dict):
        result = copy.deepcopy(default)
        if isinstance(current, dict):
            for k, v in current.items():
                result[k] = schema_merge(default.get(k), v) if k in default else copy.deepcopy(v)
        return result
    if isinstance(default, list):
        return copy.deepcopy(current) if isinstance(current, list) else copy.deepcopy(default)
    return copy.deepcopy(current) if current is not None else copy.deepcopy(default)


def seed_merge(current: Any, incoming: Any) -> Any:
    """Import the supplied document profile. Non-empty imported values win once."""
    if isinstance(incoming, dict):
        result = copy.deepcopy(current) if isinstance(current, dict) else {}
        for k, v in incoming.items():
            result[k] = seed_merge(result.get(k), v)
        return result
    if isinstance(incoming, list):
        return copy.deepcopy(incoming) if incoming else copy.deepcopy(current if isinstance(current, list) else [])
    if incoming in (None, ""):
        return copy.deepcopy(current if current is not None else incoming)
    return copy.deepcopy(incoming)


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mappings (
                hostname TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                profile_key TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                PRIMARY KEY(hostname, fingerprint)
            )
            """
        )

        row = conn.execute("SELECT value FROM kv WHERE key='profile'").fetchone()
        if row:
            try:
                profile = json.loads(row["value"])
            except Exception:
                profile = copy.deepcopy(DEFAULT_PROFILE)
        else:
            profile = copy.deepcopy(DEFAULT_PROFILE)

        profile = schema_merge(DEFAULT_PROFILE, profile)

        seed = load_seed_profile()
        seed_marker = conn.execute("SELECT value FROM kv WHERE key='profile_seed_version'").fetchone()
        if seed and (not seed_marker or seed_marker["value"] != SEED_VERSION):
            profile = seed_merge(profile, seed)
            conn.execute(
                "INSERT INTO kv(key,value) VALUES('profile_seed_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (SEED_VERSION,),
            )

        conn.execute(
            "INSERT INTO kv(key,value) VALUES('profile', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(profile, ensure_ascii=False),),
        )

        cur = conn.execute("SELECT value FROM kv WHERE key='model'")
        if cur.fetchone() is None:
            conn.execute("INSERT INTO kv(key, value) VALUES('model', ?)", (os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),))
        conn.commit()


init_db()

app = FastAPI(title="Job Autofill Local Service", version="0.7.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FieldInfo(BaseModel):
    id: str
    label: str = ""
    placeholder: str = ""
    name: str = ""
    type: str = "text"
    options: List[str] = Field(default_factory=list)
    context: str = ""
    fingerprint: str = ""


class MatchRequest(BaseModel):
    page_url: str = ""
    fields: List[FieldInfo]
    use_ai: bool = True


class MatchResult(BaseModel):
    id: str
    profile_key: Optional[str] = None
    value: Any = None
    fill_value: Any = None
    confidence: float = 0.0
    source: str = "unmatched"
    reason: str = ""


class ProfilePayload(BaseModel):
    profile: Dict[str, Any]


class ModelPayload(BaseModel):
    model: str


class FeedbackPayload(BaseModel):
    page_url: str
    fingerprint: str
    profile_key: str
    confidence: float = 1.0


class RepeatablePlanRequest(BaseModel):
    kind: str
    controls: List[FieldInfo]
    record: Dict[str, Any] = Field(default_factory=dict)
    use_ai: bool = True


class RepeatableOptionRequest(BaseModel):
    kind: str
    field_label: str = ""
    record_key: str = ""
    value: Any = None
    options: List[str] = Field(default_factory=list)
    record: Dict[str, Any] = Field(default_factory=dict)
    use_ai: bool = True


def normalize_text(text: Any) -> str:
    s = str(text or "").strip().lower()
    s = re.sub(r"[\s\u3000:：*＊()（）\[\]【】_\-]+", "", s)
    return s


def get_profile() -> Dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key='profile'").fetchone()
    return json.loads(row["value"]) if row else copy.deepcopy(DEFAULT_PROFILE)


def get_model() -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key='model'").fetchone()
    return row["value"] if row else os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")


def get_by_path(data: Any, path: str) -> Any:
    cur = data
    tokens = re.findall(r"([^.\[\]]+)|\[(\d+)\]", path)
    for name, idx in tokens:
        if name:
            if not isinstance(cur, dict) or name not in cur:
                return None
            cur = cur[name]
        else:
            i = int(idx)
            if not isinstance(cur, list) or i >= len(cur):
                return None
            cur = cur[i]
    return cur


def value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return True


def field_text(field: FieldInfo) -> str:
    return " ".join(filter(None, [field.label, field.placeholder, field.name, field.context]))[:600]


def alias_score(text: str, alias: str) -> float:
    nt = normalize_text(text)
    na = normalize_text(alias)
    if not nt or not na:
        return 0.0
    if nt == na:
        return 1.0
    if na in nt:
        return min(0.98, 0.86 + min(len(na), 12) * 0.01)
    if nt in na and len(nt) >= 3:
        return 0.82
    return SequenceMatcher(None, nt, na).ratio() * 0.75


def local_match(field: FieldInfo, profile: Dict[str, Any]) -> Optional[MatchResult]:
    text = field_text(field)
    normalized_context = normalize_text(" ".join([field.label, field.context]))
    campus_context = any(
        marker in normalized_context
        for marker in ("校园经历", "校园活动", "学生干部", "学生工作", "社团经历")
    )
    best_key = None
    best_score = 0.0
    best_alias = ""
    for key, aliases in FIELD_DEFS.items():
        value = get_by_path(profile, key)
        if not value_present(value):
            continue
        for alias in aliases:
            if key in {"campus_experience.start_date", "campus_experience.end_date"} and alias in {"开始时间", "结束时间"} and not campus_context:
                continue
            score = alias_score(text, alias)
            if score > best_score:
                best_key, best_score, best_alias = key, score, alias
    if best_key and best_score >= 0.74:
        value = get_by_path(profile, best_key)
        return MatchResult(
            id=field.id,
            profile_key=best_key,
            value=value,
            fill_value=resolve_option(value, field.options),
            confidence=round(best_score, 3),
            source="rule",
            reason=f"规则匹配：{best_alias}",
        )
    return None


def resolve_option(value: Any, options: List[str]) -> Any:
    if not options:
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return value

    raw_values = value if isinstance(value, list) else [value]
    best_option = None
    best_score = 0.0

    for raw in raw_values:
        nr = normalize_text(raw)
        if not nr:
            continue

        aliases = [str(raw)]
        for canonical, vals in OPTION_ALIASES.items():
            if nr == normalize_text(canonical) or any(nr == normalize_text(v) for v in vals):
                aliases.extend(vals)
                aliases.append(canonical)

        for option in options:
            no = normalize_text(option)
            for alias in aliases:
                na = normalize_text(alias)
                score = 0.0
                if no == na:
                    score = 1.0
                elif na and (na in no or no in na):
                    score = 0.92
                else:
                    score = SequenceMatcher(None, no, na).ratio()
                if score > best_score:
                    best_score, best_option = score, option

    return best_option if best_option is not None and best_score >= 0.58 else (str(raw_values[0]) if raw_values else "")


def get_saved_mapping(hostname: str, fingerprint: str) -> Optional[str]:
    if not hostname or not fingerprint:
        return None
    with db() as conn:
        row = conn.execute(
            "SELECT profile_key FROM mappings WHERE hostname=? AND fingerprint=?",
            (hostname, fingerprint),
        ).fetchone()
    return row["profile_key"] if row else None



def repeatable_key_local(kind: str, field: FieldInfo) -> Optional[Dict[str, Any]]:
    defs = REPEATABLE_FIELD_DEFS.get(kind)
    if not defs:
        return None
    text = field_text(field)
    best_key: Optional[str] = None
    best_alias = ""
    best_score = 0.0
    for key, aliases in defs.items():
        for alias in aliases:
            score = alias_score(text, alias)
            if score > best_score:
                best_key, best_alias, best_score = key, alias, score
    if best_key and best_score >= 0.74:
        return {"record_key": best_key, "confidence": round(best_score, 3), "reason": f"规则匹配：{best_alias}"}
    return None


def repeatable_value(kind: str, record: Dict[str, Any], key: str) -> Any:
    if key in record and value_present(record.get(key)):
        return record.get(key)
    default = REPEATABLE_DEFAULTS.get(kind, {}).get(key)
    return default if value_present(default) else None


def llm_repeatable_plan(kind: str, fields: List[FieldInfo]) -> Dict[str, Dict[str, Any]]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    defs = REPEATABLE_FIELD_DEFS.get(kind)
    if OpenAI is None or not api_key or not fields or not defs:
        return {}
    allowed_keys = list(defs.keys())
    safe_fields = [
        {
            "id": f.id,
            "label": f.label[:160],
            "placeholder": f.placeholder[:120],
            "name": f.name[:120],
            "type": f.type,
            "options": f.options[:40],
            "context": f.context[:220],
        }
        for f in fields
    ]
    system = (
        "你是招聘网站重复经历表单的字段语义匹配器。只判断网页字段对应哪个结构化字段，不生成候选人资料。"
        "必须严格输出 JSON。record_key 只能来自 allowed_record_keys 或 null。"
        "特别注意：工作经历表单中的‘工作类型’不能误判为获奖类型；获奖表单中的‘时间’也不能映射到工作经历日期。"
    )
    user = {
        "kind": kind,
        "allowed_record_keys": allowed_keys,
        "controls": safe_fields,
        "output_example": {"matches": [{"id": "c1", "record_key": "end_date", "confidence": 0.98, "reason": "离职时间"}]},
    }
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1400,
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        out: Dict[str, Dict[str, Any]] = {}
        for item in payload.get("matches", []):
            fid = str(item.get("id", ""))
            key = item.get("record_key")
            if key not in allowed_keys:
                continue
            try:
                conf = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                conf = 0.0
            out[fid] = {
                "record_key": key,
                "confidence": max(0.0, min(1.0, conf)),
                "reason": str(item.get("reason", "AI语义匹配"))[:200],
            }
        return out
    except Exception as exc:
        print(f"DeepSeek repeatable plan failed: {exc}")
        return {}


def local_repeatable_option(kind: str, record_key: str, value: Any, options: List[str], record: Dict[str, Any]) -> Optional[str]:
    if not options:
        return None
    candidates: List[Any] = []
    if value_present(value):
        candidates.append(value)
    # ATSes disagree on the meaning of “工作类型”. Some mean employment type,
    # others mean job function. Use the actual role as a safe local fallback.
    if kind == "internships" and record_key == "work_type":
        candidates.extend([record.get("work_type"), "实习", record.get("role")])
    best: Optional[str] = None
    best_score = 0.0
    for candidate in candidates:
        if not value_present(candidate):
            continue
        resolved = resolve_option(candidate, options)
        if resolved in options:
            nr = normalize_text(candidate)
            no = normalize_text(resolved)
            score = 1.0 if nr == no else (0.96 if nr and (nr in no or no in nr) else SequenceMatcher(None, nr, no).ratio())
            if score > best_score:
                best, best_score = resolved, score
    return best if best_score >= 0.58 else None


def llm_repeatable_option(req: RepeatableOptionRequest) -> Optional[str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if OpenAI is None or not api_key or not req.options:
        return None
    compact_record = {
        k: str(req.record.get(k, ""))[:240]
        for k in ("company", "role", "city", "work_type", "name", "level", "type", "relation", "age", "employer", "department", "position", "political_status", "is_china_post_employee")
        if value_present(req.record.get(k))
    }
    system = (
        "你负责在招聘网站下拉选项中选择最符合候选人已有结构化记录的一项。"
        "只能返回 options 中的原文，无法确定就返回 null。不要虚构经历。严格 JSON。"
    )
    user = {
        "kind": req.kind,
        "field_label": req.field_label,
        "record_key": req.record_key,
        "current_value": req.value,
        "record_context": compact_record,
        "options": req.options[:80],
        "output_example": {"choice": "软件开发", "confidence": 0.91, "reason": "岗位为软件开发"},
    }
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=500,
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        choice = payload.get("choice")
        if choice in req.options:
            try:
                conf = float(payload.get("confidence", 0))
            except (TypeError, ValueError):
                conf = 0.0
            return choice if conf >= 0.55 else None
    except Exception as exc:
        print(f"DeepSeek repeatable option failed: {exc}")
    return None

def llm_match(fields: List[FieldInfo], profile: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if OpenAI is None or not api_key or not fields:
        return {}

    allowed_keys = [k for k in FIELD_DEFS if value_present(get_by_path(profile, k))]
    if not allowed_keys:
        return {}

    safe_fields = [
        {
            "id": f.id,
            "label": f.label[:120],
            "placeholder": f.placeholder[:120],
            "name": f.name[:120],
            "type": f.type,
            "options": f.options[:30],
            "context": f.context[:220],
        }
        for f in fields
    ]

    system = (
        "你是招聘表单字段匹配器。只做字段语义分类，不猜测候选人的真实个人信息。"
        "请严格输出 json。每个字段只能映射到 allowed_profile_keys 中的一个 key，或 null。"
        "confidence 取 0~1。不要根据 options 伪造个人资料。"
        "对于重复的教育/实习记录，只有上下文明确指出第几段、最近一段、本科/硕士时才映射到对应索引；否则宁可返回 null。"
    )
    user = {
        "task": "将网页招聘表单字段映射到本地 profile schema。只返回 JSON。",
        "allowed_profile_keys": allowed_keys,
        "fields": safe_fields,
        "output_example": {
            "matches": [
                {"id": "f1", "profile_key": "basic.email", "confidence": 0.98, "reason": "字段询问电子邮箱"}
            ]
        },
    }

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2200,
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        result: Dict[str, Dict[str, Any]] = {}
        for item in payload.get("matches", []):
            field_id = str(item.get("id", ""))
            key = item.get("profile_key")
            if key not in allowed_keys:
                continue
            try:
                conf = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            result[field_id] = {
                "profile_key": key,
                "confidence": max(0.0, min(1.0, conf)),
                "reason": str(item.get("reason", "AI语义匹配"))[:200],
            }
        return result
    except Exception as exc:
        print(f"DeepSeek match failed: {exc}")
        return {}


@app.get("/api/status")
def status() -> Dict[str, Any]:
    profile = get_profile()
    return {
        "ok": True,
        "db": str(DB_PATH),
        "env_encoding": ENV_ENCODING,
        "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
        "model": get_model(),
        "profile_name": get_by_path(profile, "basic.name_cn") or "",
        "education_count": len(profile.get("education", [])),
        "internship_count": len(profile.get("internships", [])),
        "award_count": len(profile.get("awards", [])),
    }


@app.get("/api/profile")
def read_profile() -> Dict[str, Any]:
    return {"profile": get_profile()}


@app.put("/api/profile")
def update_profile(payload: ProfilePayload) -> Dict[str, Any]:
    profile = schema_merge(DEFAULT_PROFILE, payload.profile)
    with db() as conn:
        conn.execute(
            "INSERT INTO kv(key, value) VALUES('profile', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(profile, ensure_ascii=False),),
        )
        conn.commit()
    return {"ok": True, "profile": profile}


@app.put("/api/model")
def update_model(payload: ModelPayload) -> Dict[str, Any]:
    model = payload.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail="model 不能为空")
    with db() as conn:
        conn.execute(
            "INSERT INTO kv(key, value) VALUES('model', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (model,),
        )
        conn.commit()
    return {"ok": True, "model": model}


@app.post("/api/feedback")
def save_feedback(payload: FeedbackPayload) -> Dict[str, Any]:
    hostname = urlparse(payload.page_url).hostname or ""
    if payload.profile_key not in FIELD_DEFS:
        raise HTTPException(status_code=400, detail="未知 profile_key")
    if not hostname or not payload.fingerprint:
        raise HTTPException(status_code=400, detail="缺少 hostname 或 fingerprint")
    with db() as conn:
        conn.execute(
            """
            INSERT INTO mappings(hostname, fingerprint, profile_key, confidence)
            VALUES(?,?,?,?)
            ON CONFLICT(hostname, fingerprint)
            DO UPDATE SET profile_key=excluded.profile_key, confidence=excluded.confidence
            """,
            (hostname, payload.fingerprint, payload.profile_key, payload.confidence),
        )
        conn.commit()
    return {"ok": True}



@app.post("/api/repeatable/plan")
def repeatable_plan(req: RepeatablePlanRequest) -> Dict[str, Any]:
    if req.kind not in REPEATABLE_FIELD_DEFS:
        raise HTTPException(status_code=400, detail="未知重复经历类型")
    assignments: Dict[str, Dict[str, Any]] = {}
    unresolved: List[FieldInfo] = []
    for field in req.controls:
        local = repeatable_key_local(req.kind, field)
        if local:
            assignments[field.id] = {**local, "source": "rule"}
        else:
            unresolved.append(field)

    if req.use_ai and unresolved:
        for fid, item in llm_repeatable_plan(req.kind, unresolved).items():
            if item.get("confidence", 0) >= 0.55:
                assignments[fid] = {**item, "source": "ai"}

    out = []
    for field in req.controls:
        item = assignments.get(field.id)
        if not item:
            continue
        key = item["record_key"]
        value = repeatable_value(req.kind, req.record, key)
        # work_type can still be resolved later from the site's actual options.
        if not value_present(value) and not (req.kind == "internships" and key == "work_type"):
            continue
        out.append({
            "id": field.id,
            "record_key": key,
            "value": value,
            "fill_value": resolve_option(value, field.options) if value_present(value) else None,
            "confidence": item.get("confidence", 0),
            "source": item.get("source", "rule"),
            "reason": item.get("reason", ""),
        })
    return {
        "assignments": out,
        "stats": {
            "total": len(req.controls),
            "matched": len(out),
            "ai": sum(1 for x in out if x.get("source") == "ai"),
        },
    }


@app.post("/api/repeatable/choose-option")
def repeatable_choose_option(req: RepeatableOptionRequest) -> Dict[str, Any]:
    if req.kind not in REPEATABLE_FIELD_DEFS:
        raise HTTPException(status_code=400, detail="未知重复经历类型")
    if req.record_key not in REPEATABLE_FIELD_DEFS[req.kind]:
        raise HTTPException(status_code=400, detail="未知重复经历字段")
    options = [str(x) for x in req.options if str(x).strip()][:80]
    local = local_repeatable_option(req.kind, req.record_key, req.value, options, req.record)
    if local:
        return {"choice": local, "source": "rule"}
    if req.use_ai:
        choice = llm_repeatable_option(req.model_copy(update={"options": options}))
        if choice:
            return {"choice": choice, "source": "ai"}
    return {"choice": None, "source": "unmatched"}


@app.post("/api/match")
def match_fields(req: MatchRequest) -> Dict[str, Any]:
    profile = get_profile()
    hostname = urlparse(req.page_url).hostname or ""
    results: Dict[str, MatchResult] = {}
    unresolved: List[FieldInfo] = []

    for field in req.fields:
        saved_key = get_saved_mapping(hostname, field.fingerprint)
        if saved_key and value_present(get_by_path(profile, saved_key)):
            value = get_by_path(profile, saved_key)
            results[field.id] = MatchResult(
                id=field.id,
                profile_key=saved_key,
                value=value,
                fill_value=resolve_option(value, field.options),
                confidence=1.0,
                source="history",
                reason="命中该网站已保存字段映射",
            )
            continue

        local = local_match(field, profile)
        if local:
            results[field.id] = local
        else:
            unresolved.append(field)

    ai_results = llm_match(unresolved, profile) if req.use_ai else {}
    for field in unresolved:
        ai = ai_results.get(field.id)
        if ai and ai["confidence"] >= 0.55:
            key = ai["profile_key"]
            value = get_by_path(profile, key)
            results[field.id] = MatchResult(
                id=field.id,
                profile_key=key,
                value=value,
                fill_value=resolve_option(value, field.options),
                confidence=round(ai["confidence"], 3),
                source="ai",
                reason=ai["reason"],
            )
        else:
            results[field.id] = MatchResult(id=field.id)

    ordered = [results[f.id].model_dump() for f in req.fields]
    return {
        "matches": ordered,
        "stats": {
            "total": len(req.fields),
            "matched": sum(1 for r in ordered if r.get("profile_key")),
            "rule": sum(1 for r in ordered if r.get("source") == "rule"),
            "history": sum(1 for r in ordered if r.get("source") == "history"),
            "ai": sum(1 for r in ordered if r.get("source") == "ai"),
        },
    }


@app.get("/demo", response_class=HTMLResponse)
def demo() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>秋招助手 Demo</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#222}
form{display:grid;gap:16px}.row,.form-item{display:grid;gap:6px}input,select,textarea{padding:10px;border:1px solid #bbb;border-radius:8px;font-size:15px}
fieldset,.repeat-section{border:1px solid #ddd;border-radius:10px;padding:16px;margin:22px 0}button{padding:10px 18px;cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.section-head{display:flex;justify-content:space-between;align-items:center;gap:16px}.editor{margin-top:16px;padding-top:16px;border-top:1px dashed #ccc}.editor-actions{display:flex;gap:12px;margin-top:14px}.record{padding:10px 0;border-top:1px solid #eee}.muted{color:#777}
@media(max-width:650px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>秋招表单测试页</h1>
<p>当前项目已带入本地档案。插件会先填写普通字段，再自动处理需要“添加 → 填写 → 确认 → 再添加”的重复经历。</p>
<form id="basic-form">
  <div class="grid">
    <div class="row"><label for="cn">中文姓名</label><input id="cn" name="real_name" placeholder="请输入中文姓名" /></div>
    <div class="row"><label for="phone">手机号码</label><input id="phone" name="mobile" placeholder="请输入手机号" /></div>
    <div class="row"><label for="mail">电子邮箱</label><input id="mail" type="email" name="email" /></div>
    <div class="row"><label for="ethnicity">民族</label><input id="ethnicity" name="ethnicity" /></div>
    <div class="row"><label for="address">现住址</label><input id="address" name="current_address" /></div>
    <div class="row"><label for="marital">婚姻情况</label><select id="marital"><option value="">请选择</option><option>未婚</option><option>已婚</option></select></div>
    <div class="row"><label for="school">毕业院校</label><input id="school" name="school" /></div>
    <div class="row"><label for="major">所学专业</label><input id="major" name="major" /></div>
    <div class="row"><label for="degree">最高学历</label><select id="degree" name="degree"><option value="">请选择</option><option>大学本科</option><option>硕士研究生</option><option>博士研究生</option></select></div>
    <div class="row"><label for="undergrad">本科院校</label><input id="undergrad" name="undergraduate_school" /></div>
    <div class="row"><label for="cet6">CET6成绩</label><input id="cet6" name="cet6" /></div>
    <div class="row"><label for="emergency">紧急联系人姓名</label><input id="emergency" name="emergency_contact" /></div>
  </div>
  <fieldset><legend>性别</legend><label><input type="radio" name="gender" value="男" /> 男</label> <label><input type="radio" name="gender" value="女" /> 女</label></fieldset>
</form>

<section id="internship-section" class="repeat-section">
  <div class="section-head"><h2>实习（工作）及社会经历</h2><button type="button" class="top-add" data-add="internship">＋ 添加</button></div>
  <div class="muted">测试“逐条添加”流程。插件应自动录入 3 条实习。</div>
  <div class="records" data-records="internship"></div>
  <div class="editor-host" data-editor="internship"></div>
</section>

<section id="award-section" class="repeat-section">
  <div class="section-head"><h2>获奖经历</h2><button type="button" class="top-add" data-add="award">＋ 添加</button></div>
  <div class="muted">插件应自动录入本地档案中的 6 条奖项。</div>
  <div class="records" data-records="award"></div>
  <div class="editor-host" data-editor="award"></div>
</section>
<section id="family-section" class="repeat-section">
  <div class="section-head"><h2>家庭关系</h2><button type="button" class="top-add" data-add="family">＋ 添加</button></div>
  <div class="muted">插件应先添加父亲，再添加母亲。</div>
  <div class="records" data-records="family"></div>
  <div class="editor-host" data-editor="family"></div>
</section>

<script>
(function(){
  const internshipEditor = `
    <div class="editor internship-editor">
      <div class="grid">
        <div class="form-item"><label>工作类型</label><select name="work_type"><option value="">请选择工作类型</option><option>实习</option><option>全职</option><option>兼职</option></select></div>
        <div class="form-item"><label>工作单位</label><input name="company" placeholder="请填写工作单位"></div>
        <div class="form-item"><label>岗位</label><input name="role" placeholder="请填写岗位"></div>
        <div class="form-item"><label>入职时间</label><input name="start_date" placeholder="请选择入职时间"></div>
        <div class="form-item"><label>离职时间</label><input name="end_date" placeholder="请选择离职时间"></div>
        <div class="form-item"><label>主要工作职责和业绩</label><textarea name="description" placeholder="请填写主要工作职责和业绩"></textarea></div>
        <div class="form-item"><label>职位月薪(税前)</label><input name="salary" placeholder="请选择您在职期间的职位月薪"></div>
      </div>
      <div class="editor-actions"><button type="button" class="confirm-add">添加</button><button type="button" class="cancel-add">取消</button></div>
    </div>`;
  const awardEditor = `
    <div class="editor award-editor">
      <div class="grid">
        <div class="form-item"><label>时间</label><input name="date" placeholder="请选择时间"></div>
        <div class="form-item"><label>奖项名称</label><input name="name" placeholder="请填写奖项名称"></div>
      </div>
      <div class="editor-actions"><button type="button" class="confirm-add">添加</button><button type="button" class="cancel-add">取消</button></div>
    </div>`;
  const familyEditor = `
    <div class="editor family-editor">
      <div class="grid">
        <div class="form-item"><label>与本人关系</label><select name="relation"><option value="">请选择</option><option>父亲</option><option>母亲</option></select></div>
        <div class="form-item"><label>亲属姓名</label><input name="name" placeholder="请填写亲属姓名"></div>
        <div class="form-item"><label>年龄</label><input name="age" placeholder="请填写年龄"></div>
        <div class="form-item"><label>工作单位</label><input name="employer" placeholder="请填写工作单位"></div>
        <div class="form-item"><label>工作部门</label><input name="department" placeholder="请填写工作部门"></div>
        <div class="form-item"><label>职务</label><input name="position" placeholder="请填写职务"></div>
        <div class="form-item"><label>联系电话</label><input name="phone" placeholder="请填写联系电话"></div>
        <div class="form-item"><label>政治面貌</label><select name="political_status"><option value="">请选择</option><option>群众</option><option>中共党员</option></select></div>
        <div class="form-item"><label>是否为中国邮政系统职工</label><select name="is_china_post_employee"><option value="">请选择</option><option>是</option><option>否</option></select></div>
      </div>
      <div class="editor-actions"><button type="button" class="confirm-add">添加</button><button type="button" class="cancel-add">取消</button></div>
    </div>`;

  function openEditor(kind){
    const host=document.querySelector(`[data-editor="${kind}"]`);
    if(host.querySelector('.editor')) return;
    host.innerHTML=kind==='internship'?internshipEditor:(kind==='award'?awardEditor:familyEditor);
    const editor=host.querySelector('.editor');
    editor.querySelector('.cancel-add').addEventListener('click',()=>host.innerHTML='');
    editor.querySelector('.confirm-add').addEventListener('click',()=>{
      const values=Object.fromEntries([...editor.querySelectorAll('[name]')].map(x=>[x.name,x.value]));
      const identity=kind==='internship'?values.company:values.name;
      if(!identity) return;
      const row=document.createElement('div');
      row.className='record';
      row.textContent=kind==='internship'
        ? `${values.company}｜${values.role}｜${values.start_date} ~ ${values.end_date}`
        : (kind==='award' ? `${values.date}｜${values.name}` : `${values.relation}｜${values.name}｜${values.employer}｜${values.phone}`);
      document.querySelector(`[data-records="${kind}"]`).appendChild(row);
      host.innerHTML='';
    });
  }
  document.querySelector('[data-add="internship"]').addEventListener('click',()=>openEditor('internship'));
  document.querySelector('[data-add="award"]').addEventListener('click',()=>openEditor('award'));
  document.querySelector('[data-add="family"]').addEventListener('click',()=>openEditor('family'));
})();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    profile = get_profile()
    name = get_by_path(profile, "basic.name_cn") or "未设置"
    return f"""
<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>Job Autofill</title>
<body style='font-family:system-ui;max-width:720px;margin:40px auto;padding:0 20px'>
<h1>Job Autofill Local Service</h1>
<p>服务已启动。当前档案：<strong>{name}</strong></p>
<ul><li><a href='/demo'>测试表单 /demo</a></li><li><a href='/docs'>API 文档 /docs</a></li></ul>
</body></html>
"""
