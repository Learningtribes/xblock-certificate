"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources
from django.template import Context, Template
from django.contrib.auth.models import User
from django.test.client import RequestFactory

from xblock.core import XBlock
from xblock.fields import Scope, String, Integer, Dict
from xblock.fragment import Fragment
from mako.template import Template as MakoTemplate

from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory


@XBlock.needs('user', 'i18n')
class CertificateXBlock(XBlock):
    """
    TO-DO: document what your XBlock does.
    """

    # Fields are defined on the class.  You can access them in your code as
    # self.<fieldname>.

    display_name = String(
        display_name="Display Name",
        help="",
        default="icxblock",
        scope=Scope.content,
    )
    assignment_type = String(help="", default="", scope=Scope.content)
    success_threshold = Integer(help="", default=0, scope=Scope.content)
    title = String(help="", default="Intermediate Certificate", scope=Scope.content)
    issue_date = String(help="", default="", scope=Scope.content)
    assignment_type_override = String(help="", default="", scope=Scope.content)
    platform_name_override = String(help="", default="", scope=Scope.content)
    html_template = String(help="", default="", scope=Scope.content)
    intermediate_certificate = Dict(default={}, scope=Scope.user_state_summary)

    has_author_view = True

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def _get_mock_request(self, student):
        """
        Make a fake request because grading code expects to be able to look at
        the request. We have to attach the correct user to the request before
        grading that student.
        """
        request = RequestFactory().get('/')
        request.user = student
        return request

    def _calculate_score_for_modules(self, user, course, modules):
        from courseware.model_data import FieldDataCache, ScoresClient
        from courseware.module_render import get_module_for_descriptor
        from opaque_keys.edx.locator import BlockUsageLocator
        modules = [m for m in modules]
        locations = [
            BlockUsageLocator(
                course_key=course.id,
                block_type=module.location.block_type,
                block_id=module.location.block_id
            )
            if isinstance(module.location, BlockUsageLocator) and module.location.version
            else module.location
            for module in modules
        ]

        scores_client = ScoresClient(course.id, user.id)
        scores_client.fetch_scores(locations)

        # Iterate over all of the exam modules to get score percentage of user for each of them
        module_scores = []
        ignore_categories = ['course', 'chapter', 'sequential', 'vertical', 'randomize']
        for index, module in enumerate(modules):
            if module.category not in ignore_categories and (module.graded or module.has_score):
                module_score = scores_client.get(locations[index])
                if module_score:
                    correct = module_score.correct or 0
                    total = module_score.total or 1
                    module_scores.append((correct, total))
                else:
                    field_data_cache = FieldDataCache([module], course.id, user)
                    try:
                        module_instance = get_module_for_descriptor(
                            user,
                            self._get_mock_request(user),
                            module,
                            field_data_cache,
                            course.id,
                            course=course
                        )
                        data = module_instance.get_score()
                        module_scores.append((data.get('score'), data.get('total')))
                    except:
                        continue


        return module_scores

    def get_module_score(self, user, course, module):
        """
        Collects all children of the given module and calculates the cumulative
        score for this set of modules for the given user.

        Arguments:
            user (User): The user
            course (CourseModule): The course
            module (XBlock): The module

        Returns:
            float: The cumulative score
        """
        from courseware.model_data import FieldDataCache
        from courseware.module_render import get_module_for_descriptor
        from util.module_utils import yield_dynamic_descriptor_descendants
        def inner_get_module(descriptor):
            """
            Delegate to get_module_for_descriptor
            """
            field_data_cache = FieldDataCache([descriptor], course.id, user)
            return get_module_for_descriptor(
                user,
                self._get_mock_request(user),
                descriptor,
                field_data_cache,
                course.id,
                course=course
            )

        modules = yield_dynamic_descriptor_descendants(
            module,
            user.id,
            inner_get_module
        )
        return self._calculate_score_for_modules(user, course, modules)


    def get_grades_summary(self):
        grades_summary = None
        try:
            if hasattr(self.runtime, 'course_id'):
                course = self.runtime.modulestore.get_course(self.runtime.course_id)
            elif hasattr(self.runtime, 'course_entry'):
                course = self.runtime.modulestore.get_course(self.runtime.course_entry.course_key)
            else:
                course = None
            if course:
                student = User.objects.prefetch_related("groups").get(id=self.runtime.user_id)
                # we get the grade_summary using lms.djangoapps.grades.course_grade_factory instead of old courseware.grades
                grades_summary = CourseGradeFactory().read(student, course).summary
        except:
            pass
        return grades_summary, course, student


    def html_args(self, student=None, course=None):
        """
        return pdf_html, success, score(percentage)
        """

        if student and course:
            grades_summary = CourseGradeFactory().read(student, course).summary
        else:
            grades_summary, course, student = self.get_grades_summary()

        point_earned = 0
        point_possible = 0
        success = False
        percentage = 0

        # replace 'totaled_scores' in grades_summary to 'grade_breakdown'
        if grades_summary and \
                'grade_breakdown' in grades_summary and \
                self.assignment_type in grades_summary.get('grade_breakdown'):

            # get the scores related to the assignment_type
            score = grades_summary.get('grade_breakdown').get(self.assignment_type)

            # (score.detail) 'Homework = 51.00% of a possible 75.00%'
            # => (possible_str) '75.00'
            # => (possible_score) 0.75
            possible_str = score['detail'].split(' ')[-1].strip('%')[:-1]
            possible_score = float(possible_str)/100
            point_earned = score['percent']
            point_possible = possible_score

            if (point_possible > 0):
                percentage = round((point_earned / point_possible) * 100, 2)
                success = percentage >= self.success_threshold

        pdf_html = None
        if success:
            # date = datetime.datetime.strptime(self.issue_date, "%m/%d/%Y")
            # day = int(date.strftime("%d"))
            # if 4 <= day <= 20 or 24 <= day <= 30:
            #     suffix = "th"
            # else:
            #     suffix = ["st", "nd", "rd"][day % 10 - 1]
            # date_string = date.strftime('%B {}{} %Y'.format(day, suffix))

            if self.issue_date:
                certificate_issue_date = self.issue_date.replace('/', '-')
            else:
                from courseware.models import StudentModule
                from lms.djangoapps.grades.context import grading_context_for_course

                # we get the sections only related to the assignment type
                assignment_sections = grading_context_for_course(course).\
                    get('all_graded_subsections_by_type').get(self.assignment_type)

                # get all the scored blocks of the assignment section
                blocks = []
                for element in assignment_sections:
                    blocks += element['scored_descendants']
                scorable_locations = [block.location for block in blocks]
                print '[scorable_locations]', scorable_locations

                # The StudentModule keeps student state for a particular
                # module in a particular course. we get the queryset of all
                # StudentModules of the blocks with the same assignment type
                scores_qset = StudentModule.objects.filter(
                    student_id=student.id,
                    course_id=course.id,
                    module_state_key__in=set(scorable_locations),
                )
                time_list = scores_qset.values_list('modified', flat=True).order_by('-modified')
                print '[time_list]', time_list
                if len(time_list) == 0:
                    certificate_issue_date = ''
                else:
                    # The latest time of user submit answer
                    certificate_issue_date = time_list[0]
                    certificate_issue_date = certificate_issue_date.strftime('%m-%d-%Y')


            # certificate_issue_date = certificate_issue_date.strftime('%m-%d-%Y')
            successful_ic = {
                str(self.runtime.user_id): {
                    'badge': self.assignment_type,
                    'title': self.title,
                    'issue_date': certificate_issue_date,
                    'success': 1,
                    'course_id': str(course.id),
                }
            }
            self.intermediate_certificate.update(successful_ic)

            pdf_string = self.html_template
            mytemplate = MakoTemplate(pdf_string)
            pdf_html = mytemplate.render(issue_date=certificate_issue_date,
                                         certificate_title=self.title,
                                         full_name=student.profile.name,
                                         assignment_type=self.assignment_type_override or self.assignment_type,
                                         platform_name=self.platform_name_override,
                                         score=percentage,
                                         threshold=self.success_threshold)
        else:
            fail_ic = {
                str(self.runtime.user_id): {
                    'badge': self.assignment_type,
                    'title': self.title,
                    'success': 0,
                }
            }
            self.intermediate_certificate.update(fail_ic)

            if student.is_staff:
                pdf_string = self.html_template
                mytemplate = MakoTemplate(pdf_string)
                pdf_html = mytemplate.render(issue_date=self.issue_date,
                                             certificate_title=self.title,
                                             full_name=student.profile.name,
                                             assignment_type=self.assignment_type_override or self.assignment_type,
                                             platform_name=self.platform_name_override,
                                             score=0,
                                             threshold=self.success_threshold)

        return pdf_html, success, percentage

    def author_view(self, context=None):
        """
        The primary view of the CertificateXBlock, shown to students
        when viewing courses.
        """

        pdf_html, success, percentage = self.html_args()

        html = get_html("static/html/icxblock.html", data={
            "_": self.ugettext,
            "success": success,
            "title": self.title,
            "type": self.assignment_type_override or self.assignment_type,
            "score": percentage,
            "pdf": pdf_html,
            "staff": self.runtime.user_is_staff
        })

        frag = Fragment(html)
        frag.add_css(self.resource_string("static/css/icxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/icxblock.js"))
        frag.initialize_js('CertificateXBlock')
        return frag

    # TO-DO: change this view to display your data your own way.
    def student_view(self, context=None):
        """
        The primary view of the CertificateXBlock, shown to students
        when viewing courses.
        """

        pdf_html, success, percentage = self.html_args()

        html = get_html("static/html/icxblock.html", data={
            "_": self.ugettext,
            "success": success,
            "title": self.title,
            "type": self.assignment_type_override or self.assignment_type,
            "score": percentage,
            "pdf": pdf_html,
            # "staff": self.runtime.user_is_staff,
            "staff": False,
        })

        frag = Fragment(html)
        frag.add_css(self.resource_string("static/css/icxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/icxblock.js"))
        frag.initialize_js('CertificateXBlock')
        return frag

    def studio_view(self, context=None):
        """
        The primary view of the TranslateMeXBlock, shown to students
        when viewing courses.
        """
        from opaque_keys.edx.keys import CourseKey
        if hasattr(self.runtime, 'course_id'):
            course_key_string = self.runtime.course_id.__str__()
        elif hasattr(self.runtime, 'course_entry'):
            course_key_string = self.runtime.course_entry.course_key.__str__()
        else:
            course_key_string = None

        grade_types = []
        if course_key_string:
            course_key = CourseKey.from_string(course_key_string)
            course = self.runtime.modulestore.get_course(course_key)
            if course:
                grade_types = [type for subgrader, type, weight in course.grader.subgraders]

        html_string = self.resource_string("static/html/icxblock_edit.html")
        template = Template(html_string)
        html = template.render(Context({
            "gradeTypes": grade_types,
            "selectedType": self.assignment_type,
            "threshold": self.success_threshold,
            "title": self.title,
            "issuedate": self.issue_date,
            "typeoverride": self.assignment_type_override,
            "platformname": self.platform_name_override,
            "htmltemplate": self.html_template
        }))
        frag = Fragment(html)
        frag.add_css(self.resource_string("static/css/icxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/icxblock_edit.js"))
        frag.initialize_js('CertificateXBlockStudio')
        return frag

    # TO-DO: change this handler to perform your own actions.  You may need more
    # than one handler, or you may not need any handlers at all.
    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        Called when submitting the form in Studio.
        """
        self.assignment_type = data.get('gradingtype')
        self.success_threshold = data.get('threshold')
        self.html_template = data.get('htmltemplate')
        self.title = data.get('title')
        self.issue_date = data.get('issuedate')
        self.assignment_type_override = data.get('typeoverride')
        self.platform_name_override = data.get('platformname')

        return {'result': 'success'}

    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("CertificateXBlock",
             """<icxblock/>
             """),
            ("Multiple CertificateXBlock",
             """<vertical_demo>
                <icxblock/>
                <icxblock/>
                <icxblock/>
                </vertical_demo>
             """),
        ]

    def get_report_html(self, user, course_key):
        pdf_html, success, percentage = self.html_args(user, course_key)
        return pdf_html


def get_html(path, data):
    tplt = MakoTemplate(pkg_resources.resource_string(__name__, path))
    return tplt.render_unicode(**data)
