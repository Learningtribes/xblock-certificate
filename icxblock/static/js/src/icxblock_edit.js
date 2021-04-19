/* Javascript for CertificateXBlock. */
function CertificateXBlockStudio(runtime, element) {

    $(element).find('.cancel-button').click(function() {
        runtime.notify('cancel', {});
        e.stopPropagation();
        e.preventDefault();
        return false;
    });

    $(element).find('.save-button').bind('click', function(e) {
        var handlerUrl = runtime.handlerUrl(element, 'studio_submit');
        var data = {
            gradingtype: $(element).find('#gradingtype').val(),
            threshold: $(element).find('#threshold').val(),
            title: $(element).find('#title').val(),
            issuedate: $(element).find('#issuedate').val(),
            typeoverride: $(element).find('#typeoverride').val(),
            platformname: $(element).find('#platformname').val(),
            htmltemplate: $(element).find('#htmltemplate').val(),
        };
        runtime.notify('save', {state: 'start'});
        $.post(handlerUrl, JSON.stringify(data)).done(function(response) {
          runtime.notify('save', {state: 'end'});
        });
        e.stopPropagation();
        e.preventDefault();
        return false;
    });

    $(function ($) {
        /* Here's where you'd do things on page load. */
        $( "#issuedate" ).datepicker();

        if (LearningTribes && LearningTribes.QuestionMark) {
            $wrappers = $(element).find('.list-input .field .question-mark-wrapper')
            $wrappers.each(function(i, wrapper){
                new LearningTribes.QuestionMark(wrapper)
            })
        }

    });
}
