/* Javascript for CertificateXBlock. */
function CertificateXBlock(runtime, element) {

    $(element).find('.download-button').click(function() {
        var html = $(element).find('#certificate-data').html();
        var printHeader = $(element).find('#print-header').html();
        var printHeaderCss = $(element).find('#print-header-css').html();
        var newWindow = window.open();
        newWindow.document.write(html);
        $(newWindow.document).find('head').append(printHeaderCss);
        newWindow.document.body.innerHTML = printHeader + newWindow.document.body.innerHTML;
        newWindow.document.close();
    });

    $(element).find('.preview-button').click(function() {
        var html = $(element).find('#staff-preview').html();
        var printHeader = $(element).find('#print-header').html();
        var printHeaderCss = $(element).find('#print-header-css').html();
        var newWindow = window.open();
        newWindow.document.write(html);
        $(newWindow.document).find('head').append(printHeaderCss);
        newWindow.document.body.innerHTML = printHeader + newWindow.document.body.innerHTML;
        newWindow.document.close();
    });

    $(function ($) {
        /* Here's where you'd do things on page load. */
    });
}
