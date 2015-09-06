import os, uuid

GENDER = (
    ('M', 'Male'),
    ('F', 'Female'),
    ('U', 'Prefer not to say')
)

APPLICATION_STATUS = (
    ('P', 'Pending'),
    ('D', 'Denied'),
    ('A', 'Accepted'),
)

CITIZEN_REFUGE_ADDITIONAL = (
    (1, 'provide free food'),
    (2, 'share advice about the city and its services'),
    (3, 'hang out with the refugees'),
)

def unique_media_path(root):
    def file_path(instance, filename):
        ext = filename.split('.')[-1]
        filename = "%s.%s" % (uuid.uuid4(), ext)
        return os.path.join('media', root, filename)
    return file_path
