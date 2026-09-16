from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "autofill.db"
SEED_PATH = DATA_DIR / "profile_seed.json"
SEED_HASH_KEY = "profile_seed_hash"
EDITOR_PATH = ROOT / "backend" / "profile_editor.html"
DATA_DIR.mkdir(parents=True, exist_ok=True)


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
        "age": "",
        "birth_place": "",
        "political_status": "",
        "party_join_date": "",
        "ethnicity": "",
        "height_cm": "",
        "weight_kg": "",
        "hometown": "",
        "is_beijing_household": "",
        "household_location": "",
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
            "school_location_type": "",
            "school_location": "",
            "degree": "",
            "academic_degree": "",
            "college": "",
            "major": "",
            "research_direction": "",
            "courses": "",
            "study_form": "",
            "start_date": "",
            "end_date": "",
            "expected_degree_date": "",
            "first_degree": "",
            "full_time": "",
            "exchange_program": "",
            "gpa": "",
            "ranking": "",
            "education_type": "",
            "study_length_years": "",
            "integrated_training": "",
            "discipline_category": "",
            "training_mode": "",
            "overseas_study_experience": "",
            "graduation_project": "",
            "school_country": "",
            "is_main_study_experience": "",
        }
    ],
    "internships": [],
    "projects": [],
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
    "self_evaluation": {"content": ""},
    "career_planning": {"content": ""},
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
        "projects_text": "",
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
    "basic.age": ["年龄", "周岁", "age"],
    "basic.birth_place": ["出生地", "出生地点", "出生所在地", "place of birth", "birth place"],
    "basic.political_status": ["政治面貌", "政治身份", "political status"],
    "basic.party_join_date": ["入党团时间", "入党时间", "入团时间", "加入党团时间", "政治面貌取得时间"],
    "basic.ethnicity": ["民族", "民族信息", "ethnicity"],
    "basic.height_cm": ["身高", "身高cm", "height"],
    "basic.weight_kg": ["体重", "体重kg", "weight"],
    "basic.hometown": ["籍贯", "祖籍", "native place", "hometown"],
    "basic.is_beijing_household": ["是否北京户口", "是否为北京户口", "北京户口", "是否北京户籍"],
    "basic.household_location": ["户口所在地", "户籍所在地", "当前户口所在地", "当前户籍所在地"],
    "basic.student_origin": ["高考生源地", "生源地", "生源所在地", "生源地区", "student origin"],
    "basic.current_city": ["现居地", "现居城市", "现居住城市", "当前城市", "current city", "city of residence"],
    "basic.current_address": ["现住址", "现居住址", "现居地址", "当前住址", "current address"],
    "basic.marital_status": ["婚姻情况", "婚姻状况", "marital status"],
    "basic.health_status": ["健康状况", "健康情况", "身体状况", "health status"],
    "basic.pre_enrollment_household_location": ["入学前户口所在地", "入学前户籍所在地", "入学前户口", "入学前户籍"],
    "basic.mailing_address": ["通讯地址", "通信地址", "邮寄地址", "联系地址", "mailing address", "postal address"],
    "basic.postal_code": ["邮政编码", "邮编", "邮递区号", "postal code", "zip code"],

    "education[0].school": ["毕业院校", "最高学历院校", "研究生院校", "硕士院校", "学校", "院校", "university", "school", "college"],
    "education[0].school_location_type": ["办学属地", "学校办学属地", "院校办学属地", "办学所在地", "学校属地"],
    "education[0].school_location": ["学校所在地", "院校所在地", "学校地点", "院校地点"],
    "education[0].degree": ["学历", "最高学历", "全日制最高学历", "最高全日制学历", "研究生学历", "硕士学历", "education level"],
    "education[0].academic_degree": ["学位", "最高学位", "研究生学位", "硕士学位", "academic degree"],
    "education[0].college": ["研究生院系", "硕士院系", "最高学历院系", "院系", "学院"],
    "education[0].major": ["专业", "所学专业", "最高学历专业", "研究生专业", "硕士专业", "major", "field of study"],
    "education[0].research_direction": ["研究方向", "硕士研究方向", "研究生研究方向", "research direction", "research area"],
    "education[0].courses": ["专业课程", "主要课程", "研究生专业课程", "硕士专业课程", "major courses", "core courses"],
    "education[0].study_form": ["学习形式", "学习方式", "就读形式", "研究生学习形式", "硕士学习形式"],
    "education[0].start_date": ["研究生入学时间", "硕士入学时间", "最高学历入学时间", "入学时间", "入学日期", "enrollment date"],
    "education[0].end_date": ["毕业时间", "预计毕业时间", "最高学历毕业时间", "研究生毕业时间", "graduation date"],
    "education[0].expected_degree_date": ["拟取得学位时间", "预计取得学位时间", "学位取得时间", "预计获得学位时间"],
    "education[0].full_time": ["最高学历是否全日制", "研究生是否全日制", "是否全日制"],
    "education[0].exchange_program": ["最高学历合作交流项目", "研究生合作交流项目", "合作交流项目"],
    "education[0].gpa": ["gpa", "绩点", "平均绩点", "grade point average"],
    "education[0].ranking": ["研究生成绩排名", "最高学历成绩排名", "成绩排名", "专业排名", "ranking", "class rank"],
    "education[0].education_type": ["受教育类型", "教育类型", "研究生受教育类型", "硕士受教育类型"],
    "education[0].study_length_years": ["学制", "研究生学制", "硕士学制", "学制年限"],
    "education[0].integrated_training": ["是否贯通式培养", "贯通式培养", "贯通培养", "是否贯通培养", "研究生是否贯通式培养"],
    "education[0].discipline_category": ["学科属性", "学科门类", "学科类别", "所属学科", "研究生学科属性"],
    "education[0].training_mode": ["培养方式", "培养类型", "培养类别", "研究生培养方式"],
    "education[0].overseas_study_experience": ["该段教育经历内是否有海外学习经历", "是否有海外学习经历", "海外学习经历", "海外经历"],
    "education[0].graduation_project": ["硕士毕业设计", "硕士毕业论文", "毕业设计", "毕业论文题目", "毕业课题"],

    "education[1].school": ["本科院校", "本科学校", "本科毕业院校", "本科就读学校", "undergraduate school", "bachelor university"],
    "education[1].school_location_type": ["本科办学属地", "本科院校办学属地", "办学属地", "学校办学属地", "院校办学属地"],
    "education[1].school_location": ["本科学校所在地", "本科院校所在地", "学校所在地", "院校所在地"],
    "education[1].degree": ["本科学历", "本科层次", "本科教育学历", "undergraduate education level"],
    "education[1].academic_degree": ["本科学位", "学士学位", "本科教育学位", "undergraduate degree", "bachelor degree"],
    "education[1].college": ["本科院系", "本科院系名称", "本科所在学院"],
    "education[1].major": ["本科专业", "本科所学专业", "undergraduate major"],
    "education[1].courses": ["本科专业课程", "本科主要课程", "本科课程", "undergraduate courses"],
    "education[1].study_form": ["本科学习形式", "本科就读形式", "学习形式", "学习方式", "就读形式"],
    "education[1].start_date": ["本科入学时间", "本科开始时间"],
    "education[1].end_date": ["本科毕业时间", "本科结束时间"],
    "education[1].ranking": ["本科成绩排名", "本科专业排名"],
    "education[1].education_type": ["本科受教育类型", "本科教育类型"],
    "education[1].study_length_years": ["本科学制", "本科学制年限"],
    "education[1].integrated_training": ["本科是否贯通式培养", "本科贯通式培养", "是否贯通式培养", "贯通式培养", "贯通培养"],
    "education[1].discipline_category": ["本科学科属性", "本科学科门类", "学科属性", "学科门类", "学科类别"],
    "education[1].training_mode": ["本科培养方式", "本科培养类型", "培养方式", "培养类型", "培养类别"],
    "education[1].overseas_study_experience": ["本科是否有海外学习经历", "本科海外学习经历"],
    "education[1].graduation_project": ["本科毕业设计", "本科毕业论文", "本科毕业课题"],

    # 高中教育经历。通用标签（如“学校名称”“入学时间”）只在页面上下文明示“高中/中学”时参与匹配，
    # 防止与硕士、本科教育经历发生冲突。
    "education[2].school": ["高中学校", "高中学校名称", "高中院校", "中学名称", "学校名称", "学校"],
    "education[2].school_location_type": ["高中办学属地", "高中学校办学属地", "办学属地"],
    "education[2].school_location": ["高中所在地", "高中学校所在地", "中学所在地", "学校所在地", "院校所在地"],
    "education[2].degree": ["高中学历", "高中教育学历", "学历"],
    "education[2].study_form": ["高中学习形式", "高中就读形式", "学习形式", "学习方式"],
    "education[2].academic_degree": ["高中学位", "高中教育学位", "学位"],
    "education[2].start_date": ["高中入学时间", "高中开始时间", "入学时间"],
    "education[2].end_date": ["高中毕业时间", "高中结束时间", "毕业时间"],
    "education[2].ranking": ["高中年级排名", "高中成绩排名", "年级排名"],
    "education[2].education_type": ["高中受教育类型", "高中教育类型", "受教育类型"],
    "education[2].study_length_years": ["高中学制", "高中学制年限", "学制"],
    "education[2].integrated_training": ["高中是否贯通式培养", "是否贯通式培养", "贯通式培养"],
    "education[2].discipline_category": ["高中学科属性", "学科属性", "学科门类"],
    "education[2].training_mode": ["高中培养方式", "培养方式", "培养类型"],
    "education[2].full_time": ["高中是否全日制", "是否全日制"],
    "education[2].is_main_study_experience": ["高中是否主要学习经历", "是否主要学习经历", "主要学习经历"],
    "education[2].school_country": ["高中学校所属国家", "学校所属国家", "学校国家", "就读国家"],

    "internships[0].company": ["最近实习单位", "最近一段实习单位", "第一段实习单位", "实习单位1", "最近实践单位"],
    "internships[0].city": ["最近实习城市", "第一段实习城市", "实习城市1"],
    "internships[0].role": ["最近实习岗位", "最近实习职位", "第一段实习岗位", "实习岗位1"],
    "internships[0].start_date": ["最近实习开始时间", "第一段实习开始时间", "实习开始时间1"],
    "internships[0].end_date": ["最近实习结束时间", "第一段实习结束时间", "实习结束时间1"],
    "internships[0].description": ["最近实习内容", "最近实践内容", "第一段实习内容", "实习内容1"],

    # 项目/科研经历：仅对明确指向“第一/最近项目”或“科研项目”的字段做数组项映射；
    # 泛化的“项目经历/科研经历”优先使用 summaries.projects_text，避免重复表单误填。
    "projects[0].name": ["最近项目名称", "第一项目名称", "项目1名称", "项目名称1", "物流管理系统项目名称"],
    "projects[0].type": ["第一项目类型", "项目1类型", "项目类型1"],
    "projects[0].start_date": ["最近项目开始时间", "第一项目开始时间", "项目1开始时间"],
    "projects[0].end_date": ["最近项目结束时间", "第一项目结束时间", "项目1结束时间"],
    "projects[0].tech_stack": ["最近项目技术栈", "第一项目技术栈", "项目1技术栈", "项目技术栈1"],
    "projects[0].description": ["最近项目描述", "第一项目描述", "项目1描述", "项目内容1"],
    "projects[0].result": ["第一项目成果", "项目1成果"],

    "projects[1].name": ["科研项目名称", "科研经历项目名称", "第二项目名称", "项目2名称", "项目名称2"],
    "projects[1].type": ["科研项目类型", "第二项目类型", "项目2类型"],
    "projects[1].start_date": ["科研项目开始时间", "第二项目开始时间", "项目2开始时间"],
    "projects[1].end_date": ["科研项目结束时间", "第二项目结束时间", "项目2结束时间"],
    "projects[1].tech_stack": ["科研项目技术栈", "第二项目技术栈", "项目2技术栈"],
    "projects[1].description": ["科研项目描述", "科研项目内容", "第二项目描述", "项目2描述"],
    "projects[1].result": ["科研成果", "论文成果", "项目成果", "录用情况", "科研项目成果"],

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

    "self_evaluation.content": ["自我评价", "自我评价内容", "个人评价", "个人总结", "综合评价", "自我介绍", "self evaluation", "self assessment"],
    "career_planning.content": ["职业规划", "职业发展规划", "未来职业规划", "未来五年职业规划", "五年职业规划", "就业规划", "职业目标", "career planning", "career plan"],

    "summaries.education_text": ["教育经历", "教育背景", "学习经历"],
    "summaries.internships_text": ["实习经历", "实习经验", "社会实践", "实践经历", "工作实践经历"],
    "summaries.projects_text": ["项目经历", "项目经验", "科研经历", "项目与科研经历", "科研项目", "主要项目", "project experience", "research experience"],
    "summaries.student_activities_text": ["社团经历", "学生工作", "学生社团活动", "校园活动"],
    "summaries.awards_text": ["个人荣誉", "获奖情况", "奖项", "荣誉奖励", "荣誉奖项"],
    "summaries.skills_text": ["技能水平", "技能情况", "语言水平", "外语水平"],
    "summaries.personality_text": ["性格", "性格描述", "用五个词描述性格", "五个词语描述您的性格", "personality"],

    "job_preferences.cities": ["意向城市", "期望城市", "工作地点", "意向工作地点", "期望工作地点", "preferred city", "work location"],
    "job_preferences.job_types": ["意向岗位", "期望岗位", "职位类别", "求职方向", "desired role", "job type"],
    "job_preferences.salary": ["期望薪资", "期望年薪", "期望月薪", "期望薪资范围", "期望薪资范围税前月薪", "税前期望月薪", "薪资期望", "expected salary", "salary expectation"],
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
    "projects": {
        "name": ["项目名称", "课题名称", "科研项目名称", "名称"],
        "type": ["项目类型", "经历类型", "项目类别", "类型"],
        "role": ["项目角色", "担任角色", "职责", "角色"],
        "start_date": ["项目开始时间", "开始时间", "起始时间", "开始日期"],
        "end_date": ["项目结束时间", "结束时间", "终止时间", "结束日期"],
        "tech_stack": ["技术栈", "项目技术栈", "使用技术", "技术框架", "开发技术"],
        "description": ["项目内容", "项目描述", "项目简介", "主要内容", "项目职责"],
        "result": ["项目成果", "科研成果", "论文成果", "项目业绩", "成果"],
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
    "projects": {},
    "awards": {},
    "family": {},
}

OPTION_ALIASES = {
    "身份证": ["身份证", "居民身份证", "中华人民共和国居民身份证"],
    "健康": ["健康", "良好", "身体健康"],
    "全日制教育": ["全日制教育", "全日制", "普通全日制"],
    "无": ["无", "没有", "否", "none", "no"],
    "其他": ["其他", "其它", "other"],
    "高中": ["高中", "普通高中", "高级中学", "senior high school", "high school"],
    "全日制统招": ["全日制统招", "统招", "普通全日制", "全日制"],
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


def profile_seed_hash(profile: Dict[str, Any]) -> str:
    canonical = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_seed_profile(profile: Dict[str, Any]) -> None:
    """Atomically persist the editable profile to data/profile_seed.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SEED_PATH.with_suffix(SEED_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, SEED_PATH)


def ensure_seed_file() -> None:
    """Create an empty profile_seed.json on first run when data/ is new."""
    if not SEED_PATH.exists():
        write_seed_profile(copy.deepcopy(DEFAULT_PROFILE))


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


REPEATABLE_RECORD_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "education": copy.deepcopy(DEFAULT_PROFILE["education"][0]),
    "internships": {
        "company": "", "city": "", "role": "", "work_type": "",
        "start_date": "", "end_date": "", "contact_name": "", "contact_phone": "",
        "salary": "", "description": "",
    },
    "projects": {
        "name": "", "type": "", "role": "", "start_date": "", "end_date": "",
        "tech_stack": "", "description": "", "highlights": [], "result": "",
    },
    "student_activities": {
        "organization": "", "role": "", "start_date": "", "end_date": "",
        "activities": "", "description": "",
    },
    "awards": {
        "date": "", "name": "", "type": "", "level": "", "reference": "", "details": "",
    },
}

FAMILY_MEMBER_SCHEMA: Dict[str, Any] = {
    "relation": "", "name": "", "age": "", "employer": "", "department": "",
    "position": "", "phone": "", "political_status": "", "is_china_post_employee": "",
}


def normalize_profile_schema(current: Any) -> Dict[str, Any]:
    """Return a profile containing every currently supported schema field.

    Missing supported fields are added without overwriting existing values.
    Repeated records are normalized item-by-item, so an older internship,
    project, award, education or family record also receives newly added fields.
    Unknown keys are preserved for backwards compatibility, but the web editor
    only exposes fields defined by the current application schema.
    """
    result = schema_merge(DEFAULT_PROFILE, current if isinstance(current, dict) else {})

    for collection, record_schema in REPEATABLE_RECORD_SCHEMAS.items():
        records = result.get(collection)
        if not isinstance(records, list):
            records = []
        result[collection] = [
            schema_merge(record_schema, item)
            for item in records
            if isinstance(item, dict)
        ]

    family = result.get("family")
    if not isinstance(family, dict):
        family = copy.deepcopy(DEFAULT_PROFILE["family"])
        result["family"] = family
    members = family.get("members")
    if not isinstance(members, list):
        members = []
    family["members"] = [
        schema_merge(FAMILY_MEMBER_SCHEMA, item)
        for item in members
        if isinstance(item, dict)
    ]

    return result


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

        profile = normalize_profile_schema(profile)

        ensure_seed_file()
        seed = load_seed_profile()
        if seed:
            # Older JSON files are upgraded in place: every supported missing
            # field is added while existing user values are retained.
            normalized_seed = normalize_profile_schema(seed)
            if normalized_seed != seed:
                write_seed_profile(normalized_seed)
            seed = normalized_seed

            # Re-import the seed only when profile_seed.json actually changes.
            seed_hash = profile_seed_hash(seed)
            seed_marker = conn.execute(
                "SELECT value FROM kv WHERE key=?", (SEED_HASH_KEY,)
            ).fetchone()
            if not seed_marker or seed_marker["value"] != seed_hash:
                profile = seed_merge(profile, seed)
                profile = normalize_profile_schema(profile)
                conn.execute(
                    "INSERT INTO kv(key,value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (SEED_HASH_KEY, seed_hash),
                )

        conn.execute(
            "INSERT INTO kv(key,value) VALUES('profile', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(profile, ensure_ascii=False),),
        )

        conn.commit()


init_db()

app = FastAPI(title="Job Autofill Local Service", version="1.6.0")
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


class FeedbackPayload(BaseModel):
    page_url: str
    fingerprint: str
    profile_key: str
    confidence: float = 1.0


class RepeatablePlanRequest(BaseModel):
    kind: str
    controls: List[FieldInfo]
    record: Dict[str, Any] = Field(default_factory=dict)


class RepeatableOptionRequest(BaseModel):
    kind: str
    field_label: str = ""
    record_key: str = ""
    value: Any = None
    options: List[str] = Field(default_factory=list)
    record: Dict[str, Any] = Field(default_factory=dict)


def normalize_text(text: Any) -> str:
    s = str(text or "").strip().lower()
    s = re.sub(r"[\s\u3000:：*＊()（）\[\]【】_\-]+", "", s)
    return s


def get_profile() -> Dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key='profile'").fetchone()
    return json.loads(row["value"]) if row else copy.deepcopy(DEFAULT_PROFILE)


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



GENERIC_EDUCATION_ALIASES = {
    "学校", "学校名称", "院校", "办学属地", "学校所在地", "院校所在地",
    "学历", "学位", "院系", "学院", "专业", "研究方向", "专业课程", "主要课程",
    "学习形式", "学习方式", "就读形式", "是否贯通式培养", "贯通式培养",
    "培养方式", "培养类型", "学科属性", "学科门类", "学科类别",
    "入学时间", "入学日期", "毕业时间", "毕业日期", "年级排名", "成绩排名",
    "绩点", "gpa", "是否全日制", "受教育类型", "教育类型", "学制",
}


def education_key_index(key: str) -> Optional[int]:
    m = re.match(r"education\[(\d+)\]\.", key or "")
    return int(m.group(1)) if m else None


def explicit_education_index(field: FieldInfo) -> Optional[int]:
    """Infer an education record only from explicit semantic markers."""
    text = normalize_text(" ".join([
        field.label, field.placeholder, field.name, field.context
    ]))

    if any(x in text for x in ("高中", "中学", "高级中学")):
        return 2
    if any(x in text for x in ("本科", "学士")):
        return 1
    if any(x in text for x in ("硕士", "研究生", "最高学历", "最高学位")):
        return 0
    return None


def education_index_from_peer_values(field: FieldInfo, profile: Dict[str, Any]) -> Optional[int]:
    """Use values already present in the same education form block to infer the record.

    Example: if the same form block already contains
    '北京航空航天大学 / 2024-09-01 / 2027-07-01', it should match the
    postgraduate education record even when the current label is only '学历'.
    """
    explicit = explicit_education_index(field)
    if explicit is not None:
        return explicit

    context = normalize_text(field.context)
    if not context:
        return None

    education = profile.get("education")
    if not isinstance(education, list):
        return None

    weighted_fields = (
        ("school", 5.0),
        ("start_date", 3.0),
        ("end_date", 3.0),
        ("college", 2.5),
        ("major", 2.5),
        ("research_direction", 2.0),
        ("school_location", 1.5),
        ("degree", 1.0),
        ("academic_degree", 1.0),
        ("study_form", 0.8),
        ("study_length_years", 0.8),
    )

    scores: List[tuple[int, float]] = []
    for idx, record in enumerate(education):
        if not isinstance(record, dict):
            continue

        score = 0.0
        for key, weight in weighted_fields:
            raw = record.get(key)
            if not value_present(raw):
                continue
            token = normalize_text(raw)
            # Very short values such as “是/否” are not useful identifiers.
            if len(token) < 4:
                continue
            if token in context:
                score += weight

        scores.append((idx, score))

    if not scores:
        return None

    scores.sort(key=lambda x: x[1], reverse=True)
    best_idx, best_score = scores[0]
    second_score = scores[1][1] if len(scores) > 1 else 0.0

    # Require at least one strong identifier (usually school/date) and a clear lead.
    if best_score >= 3.0 and best_score >= second_score + 1.0:
        return best_idx
    return None


def generic_education_field(field: FieldInfo) -> bool:
    """True for ambiguous labels such as simply '学历' or '毕业时间'."""
    own_text = normalize_text(" ".join([field.label, field.placeholder, field.name]))
    if not own_text:
        return False

    for alias in GENERIC_EDUCATION_ALIASES:
        na = normalize_text(alias)
        if own_text == na or own_text.startswith(na) or na in own_text:
            # Explicit stage words make it safe/non-generic.
            if any(marker in own_text for marker in (
                "高中", "中学", "本科", "硕士", "研究生", "最高学历", "最高学位"
            )):
                return False
            return True
    return False


def saved_mapping_compatible(
    field: FieldInfo,
    saved_key: str,
    profile: Dict[str, Any],
) -> bool:
    """Reject stale history when an ambiguous education field points at the wrong record."""
    idx = education_key_index(saved_key)
    if idx is None:
        return True

    inferred = education_index_from_peer_values(field, profile)
    if inferred is not None:
        return idx == inferred

    # With no record context, a generic field must never reuse a stored
    # bachelor/high-school mapping. The safe default rule is highest education.
    if generic_education_field(field) and idx != 0:
        return False

    return True


def local_match(field: FieldInfo, profile: Dict[str, Any]) -> Optional[MatchResult]:
    text = field_text(field)
    normalized_context = normalize_text(" ".join([field.label, field.context]))
    campus_context = any(
        marker in normalized_context
        for marker in ("校园经历", "校园活动", "学生干部", "学生工作", "社团经历")
    )

    inferred_education_idx = education_index_from_peer_values(field, profile)
    high_school_context = inferred_education_idx == 2 or any(
        marker in normalized_context
        for marker in ("高中", "中学", "高中教育", "高中经历")
    )

    high_school_generic_aliases = {
        "学校名称", "学校", "学历", "学位", "入学时间", "毕业时间",
        "年级排名", "受教育类型", "学制", "是否全日制",
        "是否主要学习经历", "主要学习经历", "学校所属国家", "学校国家", "就读国家",
    }

    best_key = None
    best_score = 0.0
    best_alias = ""

    for key, aliases in FIELD_DEFS.items():
        value = get_by_path(profile, key)
        if not value_present(value):
            continue

        edu_idx = education_key_index(key)

        for alias in aliases:
            if key in {"campus_experience.start_date", "campus_experience.end_date"} and alias in {"开始时间", "结束时间"} and not campus_context:
                continue

            # Generic education labels such as “学历” must follow the education
            # record inferred from peer values in the same form block.
            if edu_idx is not None and inferred_education_idx is not None:
                if alias in GENERIC_EDUCATION_ALIASES and edu_idx != inferred_education_idx:
                    continue

            # Existing protection: high-school generic labels are not allowed
            # outside a confirmed high-school context.
            if key.startswith("education[2].") and alias in high_school_generic_aliases and not high_school_context:
                continue

            identity_text = " ".join(filter(None, [field.label, field.placeholder, field.name]))
            identity_score = alias_score(identity_text, alias)
            score = max(alias_score(text, alias), identity_score)

            # 教育记录下标一致只能给“当前字段自身也像这个 alias”的候选加分。
            # 避免 context 里的学校名称/院校文字把“办学属地”等字段抢走。
            if edu_idx is not None and inferred_education_idx is not None:
                if edu_idx == inferred_education_idx and identity_score >= 0.74:
                    score = min(1.0, score + 0.14)
                elif edu_idx != inferred_education_idx:
                    score *= 0.55

            if high_school_context and key.startswith("education[2]."):
                score = min(1.0, score + 0.08)
            elif high_school_context and key.startswith(("education[0].", "education[1].")):
                score *= 0.78

            if score > best_score:
                best_key, best_score, best_alias = key, score, alias

    if best_key and best_score >= 0.74:
        value = get_by_path(profile, best_key)
        reason = f"规则匹配：{best_alias}"
        if inferred_education_idx is not None and education_key_index(best_key) is not None:
            reason += f"；同组教育记录={inferred_education_idx}"
        return MatchResult(
            id=field.id,
            profile_key=best_key,
            value=value,
            fill_value=resolve_option(value, field.options),
            confidence=round(best_score, 3),
            source="rule",
            reason=reason,
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



@app.get("/api/status")
def status() -> Dict[str, Any]:
    profile = get_profile()
    return {
        "ok": True,
        "db": str(DB_PATH),
        "profile_seed": str(SEED_PATH),
        "profile_name": get_by_path(profile, "basic.name_cn") or "",
        "education_count": len(profile.get("education", [])),
        "internship_count": len(profile.get("internships", [])),
        "project_count": len(profile.get("projects", [])),
        "award_count": len(profile.get("awards", [])),
    }


@app.get("/api/profile")
def read_profile() -> Dict[str, Any]:
    return {"profile": get_profile()}


@app.put("/api/profile")
def update_profile(payload: ProfilePayload) -> Dict[str, Any]:
    # The browser editor uses this endpoint as the single source of truth.
    # Save both SQLite (runtime reads) and profile_seed.json (human-editable source).
    profile = normalize_profile_schema(payload.profile)
    try:
        write_seed_profile(profile)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"profile_seed.json 保存失败：{exc}") from exc

    seed_hash = profile_seed_hash(profile)
    with db() as conn:
        conn.execute(
            "INSERT INTO kv(key, value) VALUES('profile', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(profile, ensure_ascii=False),),
        )
        conn.execute(
            "INSERT INTO kv(key,value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (SEED_HASH_KEY, seed_hash),
        )
        conn.commit()
    return {"ok": True, "profile": profile, "seed_path": str(SEED_PATH)}


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
    return {"choice": None, "source": "unmatched"}


@app.post("/api/match")
def match_fields(req: MatchRequest) -> Dict[str, Any]:
    profile = get_profile()
    hostname = urlparse(req.page_url).hostname or ""
    results: Dict[str, MatchResult] = {}
    unresolved: List[FieldInfo] = []

    for field in req.fields:
        saved_key = get_saved_mapping(hostname, field.fingerprint)
        if (
            saved_key
            and value_present(get_by_path(profile, saved_key))
            and saved_mapping_compatible(field, saved_key, profile)
        ):
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

    for field in unresolved:
        results[field.id] = MatchResult(id=field.id)

    ordered = [results[f.id].model_dump() for f in req.fields]
    return {
        "matches": ordered,
        "stats": {
            "total": len(req.fields),
            "matched": sum(1 for r in ordered if r.get("profile_key")),
            "rule": sum(1 for r in ordered if r.get("source") == "rule"),
            "history": sum(1 for r in ordered if r.get("source") == "history"),
        },
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/demo", response_class=HTMLResponse)
@app.get("/profile", response_class=HTMLResponse)
def profile_editor() -> str:
    """Local resume editor. /demo is kept as a compatibility alias."""
    try:
        return EDITOR_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        return f"<h1>Profile editor unavailable</h1><pre>{exc}</pre>"
