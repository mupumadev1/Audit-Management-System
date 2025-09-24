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
const deleteButtons = document.querySelectorAll('[id^="delete-button-"]');
deleteButtons.forEach(button => {
  button.addEventListener('click', function(event) {
    event.preventDefault();  // Prevent default button action


    const file_id = button.id.replace('delete-button-', '');

    fetch(button.href, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json'
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log(data);
      if (data.success) {
        alert('File deleted successfully');
        window.location.reload();
      } else {
        alert('Error deleting file: ' + (data.error || 'Unknown error'));
      }
    })
    .catch(error => {
      alert('Error deleting file: ' + error.message);
    });
  });
});
  uploadForms.forEach(form => {
    form.addEventListener('submit', function(event) {
      event.preventDefault();  // Prevent default form submit
      const batchnbr = form.id.replace('upload-form-', '');
         console.log(batchnbr)
      const project = form.dataset.projectName;
      const fileInput = document.getElementById(`document-${batchnbr}`);
      const statusDiv = document.getElementById(`upload-status-${batchnbr}`);
      const modalELm =document.getElementById(`uploadFileModal${ batchnbr }'`)
      const reference = fileInput.dataset.reference;
      console.log(reference);
      if (!fileInput.files.length) {
        statusDiv.textContent = 'Please select a file to upload.';
        return;
      }

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      formData.append('reference', reference);

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

   const additonalUploadForms = document.querySelectorAll('form[id^="additional-upload-form-"]');

  additonalUploadForms.forEach(form => {
    form.addEventListener('submit', function(event) {

      event.preventDefault();  // Prevent default form submit

      const jnldtlref = form.id.replace('additional-upload-form-', '');
      const fileInput = document.getElementById(`additional-document-${jnldtlref}`);
      const statusDiv = document.getElementById(`additional-upload-status-${jnldtlref}`);
        statusDiv.textContent = 'Please select a file to upload.';
      const reference = fileInput.dataset.reference;
    console.log(reference);
      if (!fileInput.files.length) {
        return;
      }

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      formData.append('reference', reference);
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
