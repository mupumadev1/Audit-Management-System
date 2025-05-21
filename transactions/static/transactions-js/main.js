document.addEventListener('DOMContentLoaded', function() {
  // Helper to get CSRF token from cookie (Django default)
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  const csrftoken = getCookie('csrftoken');

  // Select all upload forms (assuming multiple modals)
  const uploadForms = document.querySelectorAll('form[id^="upload-form-"]');

  uploadForms.forEach(form => {
    form.addEventListener('submit', function(event) {
      event.preventDefault();  // Prevent default form submit

      const batchnbr = form.id.replace('upload-form-', '');
      const project = form.dataset.projectName;
      const fileInput = document.getElementById(`document-${batchnbr}`);
      const statusDiv = document.getElementById(`upload-status-${batchnbr}`);
      const modalELm =document.getElementById(`uploadFileModal${ batchnbr }'`)

      if (!fileInput.files.length) {
        statusDiv.textContent = 'Please select a file to upload.';
        return;
      }

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);

      fetch(form.action, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken
        },
        body: formData
      })
      .then(response => {
        if (!response.ok) throw new Error('Upload failed');
        return response.json();
      })
      .then(data => {
        if (data.response === 'success') {
          statusDiv.textContent = 'File uploaded successfully!';
         window.location.reload()
        } else {
          statusDiv.textContent = 'Upload error: ' + (data.errors ? JSON.stringify(data.errors) : 'Unknown error');
        }
      })
      .catch(error => {
        statusDiv.textContent = 'Error uploading file: ' + error.message;
      });
    });
  });
});
