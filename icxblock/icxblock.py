"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources
from django.template import Context, Template
from django.contrib.auth.models import User
from django.test.client import RequestFactory

from xblock.core import XBlock
from xblock.fields import Scope, String, Integer
from xblock.fragment import Fragment
from mako.template import Template as MakoTemplate

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
    title = String(help="", default="", scope=Scope.content)
    issue_date = String(help="", default="", scope=Scope.content)
    assignment_type_override = String(help="", default="", scope=Scope.content)
    platform_name_override = String(help="", default="", scope=Scope.content)
    html_template = String(help="", default="", scope=Scope.content)

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


    # TO-DO: change this view to display your data your own way.
    def student_view(self, context=None):
        """
        The primary view of the CertificateXBlock, shown to students
        when viewing courses.
        """

        grades_summary = None
        try:
            # we get the grade_summary using course_widget.grades instead of courseware
            from course_widget.grades import grade
            if hasattr(self.runtime, 'course_id'):
                course = self.runtime.modulestore.get_course(self.runtime.course_id)
            elif hasattr(self.runtime, 'course_entry'):
                course = self.runtime.modulestore.get_course(self.runtime.course_entry.course_key)
            else:
                course = None
            if course:
                student = User.objects.prefetch_related("groups").get(id=self.runtime.user_id)
                grades_summary = grade(student, course)
        except:
            pass

        point_earned = 0
        point_possible = 0
        success = False
        percentage = 0

        if grades_summary and \
                'totaled_scores' in grades_summary and \
                self.assignment_type in grades_summary.get('totaled_scores'):

            # get the scores related to the assignment_type
            scores = grades_summary.get('totaled_scores').get(self.assignment_type)
            for score in scores:
                point_earned += score.earned
                point_possible += score.possible

            if (point_possible > 0):
                percentage = round((point_earned / point_possible) * 100, 2)
                success = percentage >= self.success_threshold

        html_string = self.resource_string("static/html/icxblock.html")
        template = Template(html_string)
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
                certificate_issue_date = self.issue_date
            else:
                from courseware.models import StudentModule
                from course_widget.grades import grading_context_for_course

                # we get the sections only related to the assignment type
                assignment_sections = grading_context_for_course(course).\
                    get('all_graded_sections').get(self.assignment_type)

                # get all the scored blocks of the assignment section
                blocks = []
                for element in assignment_sections:
                    blocks += element['scored_descendants']
                scorable_locations = [block.location for block in blocks]

                # The StudentModule keeps student state for a particular
                # module in a particular course. we get the queryset of all
                # StudentModules of the blocks with the same assignment type
                scores_qset = StudentModule.objects.filter(
                    student_id=student.id,
                    course_id=course.id,
                    module_state_key__in=set(scorable_locations),
                )
                time_list = scores_qset.values_list('modified', flat=True).order_by('-modified')
                # The latest time of user submit answer
                certificate_issue_date = time_list[0]

            certificate_issue_date = certificate_issue_date.strftime('%m-%d-%Y')
            pdf_string = self.html_template
            mytemplate = MakoTemplate(pdf_string)
            pdf_html = mytemplate.render(issue_date=certificate_issue_date,
                                         certificate_title=self.title,
                                         full_name=student.profile.name,
                                         assignment_type=self.assignment_type_override or self.assignment_type,
                                         platform_name=self.platform_name_override,
                                         score=percentage,
                                         threshold=self.success_threshold)
        elif self.runtime.user_is_staff:
            pdf_string = self.html_template
            mytemplate = MakoTemplate(pdf_string)
            pdf_html = mytemplate.render(issue_date=self.issue_date,
                                         certificate_title=self.title,
                                         full_name=student.profile.name,
                                         assignment_type=self.assignment_type_override or self.assignment_type,
                                         platform_name=self.platform_name_override,
                                         score=0,
                                         threshold=self.success_threshold)

        html = template.render(Context({
            "success": success,
            "title": self.title,
            "type": self.assignment_type_override or self.assignment_type,
            "score": percentage,
            "pdf": pdf_html,
            "staff": self.runtime.user_is_staff
        }))
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
                grade_types = [type for subgrader, type, weight in course.grader.sections]

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
            "threshold": self.success_threshold,
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
