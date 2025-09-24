from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models

from main_app.models import Project


# Create your models here.

class Glpost(models.Model):
    acctid = models.CharField(db_column='ACCTID', primary_key=True, max_length=45,
                              db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase. The composite primary key (ACCTID, FISCALYR, FISCALPERD, SRCECURN, SRCELEDGER, SRCETYPE, POSTINGSEQ, CNTDETAIL) found, that is not supported. The first column is selected.
    fiscalyr = models.CharField(db_column='FISCALYR', max_length=4,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    fiscalperd = models.CharField(db_column='FISCALPERD', max_length=2,
                                  db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    srcecurn = models.CharField(db_column='SRCECURN', max_length=3,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    srceledger = models.CharField(db_column='SRCELEDGER', max_length=2,
                                  db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    srcetype = models.CharField(db_column='SRCETYPE', max_length=2,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    postingseq = models.DecimalField(db_column='POSTINGSEQ', max_digits=7,
                                     decimal_places=0)  # Field name made lowercase.
    cntdetail = models.DecimalField(db_column='CNTDETAIL', max_digits=7, decimal_places=0)  # Field name made lowercase.
    audtdate = models.DecimalField(db_column='AUDTDATE', max_digits=9, decimal_places=0)  # Field name made lowercase.
    audttime = models.DecimalField(db_column='AUDTTIME', max_digits=9, decimal_places=0)  # Field name made lowercase.
    audtuser = models.CharField(db_column='AUDTUSER', max_length=8,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    audtorg = models.CharField(db_column='AUDTORG', max_length=6,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    jrnldate = models.DecimalField(db_column='JRNLDATE', max_digits=9, decimal_places=0)  # Field name made lowercase.
    batchnbr = models.CharField(db_column='BATCHNBR', max_length=6,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    entrynbr = models.CharField(db_column='ENTRYNBR', max_length=5,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    transnbr = models.DecimalField(db_column='TRANSNBR', max_digits=7, decimal_places=0)  # Field name made lowercase.
    editallowd = models.SmallIntegerField(db_column='EDITALLOWD')  # Field name made lowercase.
    consolidat = models.SmallIntegerField(db_column='CONSOLIDAT')  # Field name made lowercase.
    companyid = models.CharField(db_column='COMPANYID', max_length=8,
                                 db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    jnldtldesc = models.CharField(db_column='JNLDTLDESC', max_length=60,
                                  db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    jnldtlref = models.CharField(db_column='JNLDTLREF', max_length=60,
                                 db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    transamt = models.DecimalField(db_column='TRANSAMT', max_digits=19, decimal_places=3)  # Field name made lowercase.
    transqty = models.DecimalField(db_column='TRANSQTY', max_digits=19, decimal_places=3)  # Field name made lowercase.
    scurndec = models.CharField(db_column='SCURNDEC', max_length=1,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    scurnamt = models.DecimalField(db_column='SCURNAMT', max_digits=19, decimal_places=3)  # Field name made lowercase.
    hcurncode = models.CharField(db_column='HCURNCODE', max_length=3,
                                 db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    ratetype = models.CharField(db_column='RATETYPE', max_length=2,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    scurncode = models.CharField(db_column='SCURNCODE', max_length=3,
                                 db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    ratedate = models.DecimalField(db_column='RATEDATE', max_digits=9, decimal_places=0)  # Field name made lowercase.
    convrate = models.DecimalField(db_column='CONVRATE', max_digits=15, decimal_places=7)  # Field name made lowercase.
    ratespread = models.DecimalField(db_column='RATESPREAD', max_digits=15,
                                     decimal_places=7)  # Field name made lowercase.
    datemtchcd = models.CharField(db_column='DATEMTCHCD', max_length=1,
                                  db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    rateoper = models.CharField(db_column='RATEOPER', max_length=1,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    drilsrcty = models.SmallIntegerField(db_column='DRILSRCTY')  # Field name made lowercase.
    drilldwnlk = models.DecimalField(db_column='DRILLDWNLK', max_digits=19,
                                     decimal_places=0)  # Field name made lowercase.
    drilapp = models.CharField(db_column='DRILAPP', max_length=2,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    rptamt = models.DecimalField(db_column='RPTAMT', max_digits=19, decimal_places=3)  # Field name made lowercase.
    values = models.IntegerField(db_column='VALUES')  # Field name made lowercase.
    docdate = models.DecimalField(db_column='DOCDATE', max_digits=9, decimal_places=0)  # Field name made lowercase.
    txrptstat = models.IntegerField(db_column='TXRPTSTAT')  # Field name made lowercase.
    taxauth = models.CharField(db_column='TAXAUTH', max_length=12,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    txaccttype = models.SmallIntegerField(db_column='TXACCTTYPE')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'glpost'
        unique_together = (
            ('acctid', 'fiscalyr', 'fiscalperd', 'srcecurn', 'srceledger', 'srcetype', 'postingseq', 'cntdetail'),)


class Eneba(models.Model):
    cntbtch = models.IntegerField(db_column='CNTBTCH',
                                  primary_key=True)  # Field name made lowercase. The composite primary key (CNTBTCH, CNTITEM, DOCLINE) found, that is not supported. The first column is selected.
    cntitem = models.IntegerField(db_column='CNTITEM')  # Field name made lowercase.
    docline = models.IntegerField(db_column='DOCLINE')  # Field name made lowercase.
    audtdate = models.DecimalField(db_column='AUDTDATE', max_digits=9, decimal_places=0)  # Field name made lowercase.
    audttime = models.DecimalField(db_column='AUDTTIME', max_digits=9, decimal_places=0)  # Field name made lowercase.
    audtuser = models.CharField(db_column='AUDTUSER', max_length=8,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    audtorg = models.CharField(db_column='AUDTORG', max_length=6,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    docno = models.CharField(db_column='DOCNO', max_length=22,
                             db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    docdesc = models.CharField(db_column='DOCDESC', max_length=60,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    refdocid = models.CharField(db_column='REFDOCID', max_length=22,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    doccate = models.SmallIntegerField(db_column='DOCCATE')  # Field name made lowercase.
    keywords = models.CharField(db_column='KEYWORDS', max_length=255,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    docpath = models.CharField(db_column='DOCPATH', max_length=255,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    docname = models.CharField(db_column='DOCNAME', max_length=255,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    notes = models.CharField(db_column='NOTES', max_length=255,
                             db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    employeid = models.CharField(db_column='EMPLOYEID', max_length=16,
                                 db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    lstmntdt = models.DecimalField(db_column='LSTMNTDT', max_digits=9, decimal_places=0)  # Field name made lowercase.
    lstmntby = models.CharField(db_column='LSTMNTBY', max_length=16,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    fileid = models.CharField(db_column='FILEID', max_length=36,
                              db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    reqid = models.CharField(db_column='REQID', max_length=36,
                             db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    cntline = models.IntegerField(db_column='CNTLINE')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ENEBA'
        unique_together = (('cntbtch', 'cntitem', 'docline'),)


class Enpjd(models.Model):
    typebtch = models.CharField(db_column='TYPEBTCH', primary_key=True, max_length=2,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase. The composite primary key (TYPEBTCH, POSTSEQNCE, CNTBTCH, CNTITEM, IDDOC, FISCY, FISCPERD, CNTLINE, CNTSEQENCE) found, that is not supported. The first column is selected.
    postseqnce = models.DecimalField(db_column='POSTSEQNCE', max_digits=9,
                                     decimal_places=0)  # Field name made lowercase.
    cntbtch = models.DecimalField(db_column='CNTBTCH', max_digits=9, decimal_places=0)  # Field name made lowercase.
    cntitem = models.DecimalField(db_column='CNTITEM', max_digits=7, decimal_places=0)  # Field name made lowercase.
    iddoc = models.CharField(db_column='IDDOC', max_length=22,
                             db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    fiscy = models.SmallIntegerField(db_column='FISCY')  # Field name made lowercase.
    fiscperd = models.SmallIntegerField(db_column='FISCPERD')  # Field name made lowercase.
    cntline = models.DecimalField(db_column='CNTLINE', max_digits=7, decimal_places=0)  # Field name made lowercase.
    cntseqence = models.IntegerField(db_column='CNTSEQENCE')  # Field name made lowercase.
    audtdate = models.DecimalField(db_column='AUDTDATE', max_digits=9, decimal_places=0)  # Field name made lowercase.
    audttime = models.DecimalField(db_column='AUDTTIME', max_digits=9, decimal_places=0)  # Field name made lowercase.
    audtuser = models.CharField(db_column='AUDTUSER', max_length=8,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    audtorg = models.CharField(db_column='AUDTORG', max_length=6,
                               db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    idemp = models.CharField(db_column='IDEMP', max_length=16,
                             db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    drcr = models.CharField(db_column='DRCR', max_length=2,
                            db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    idexpctl = models.CharField(db_column='IDEXPCTL', max_length=45,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    accttype = models.SmallIntegerField(db_column='ACCTTYPE')  # Field name made lowercase.
    amtextndhc = models.DecimalField(db_column='AMTEXTNDHC', max_digits=19,
                                     decimal_places=3)  # Field name made lowercase.
    amtextndtc = models.DecimalField(db_column='AMTEXTNDTC', max_digits=19,
                                     decimal_places=3)  # Field name made lowercase.
    posted = models.SmallIntegerField(db_column='POSTED')  # Field name made lowercase.
    srcetype = models.CharField(db_column='SRCETYPE', max_length=2,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    glref = models.CharField(db_column='GLREF', max_length=60,
                             db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    gldesc = models.CharField(db_column='GLDESC', max_length=60,
                              db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    glbatnbr = models.CharField(db_column='GLBATNBR', max_length=6,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    gljrnlid = models.CharField(db_column='GLJRNLID', max_length=5,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    gltrsnbr = models.CharField(db_column='GLTRSNBR', max_length=10,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    notes = models.CharField(db_column='NOTES', max_length=30,
                             db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    sourcurr = models.CharField(db_column='SOURCURR', max_length=3,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    ratetype = models.CharField(db_column='RATETYPE', max_length=2,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    ratedate = models.DecimalField(db_column='RATEDATE', max_digits=9, decimal_places=0)  # Field name made lowercase.
    rate = models.DecimalField(db_column='RATE', max_digits=15, decimal_places=7)  # Field name made lowercase.
    values = models.IntegerField(db_column='VALUES')  # Field name made lowercase.
    datebus = models.DecimalField(db_column='DATEBUS', max_digits=9, decimal_places=0)  # Field name made lowercase.
    lstmntby = models.CharField(db_column='LSTMNTBY', max_length=8,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=250,
                                db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    dratespren = models.DecimalField(db_column='DRATESPREN', max_digits=15,
                                     decimal_places=7)  # Field name made lowercase.
    dratemtchc = models.SmallIntegerField(db_column='DRATEMTCHC')  # Field name made lowercase.
    drateoper = models.SmallIntegerField(db_column='DRATEOPER')  # Field name made lowercase.
    entryseq = models.IntegerField(db_column='ENTRYSEQ')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ENPJD'
        unique_together = (
        ('typebtch', 'postseqnce', 'cntbtch', 'cntitem', 'iddoc', 'fiscy', 'fiscperd', 'cntline', 'cntseqence'),)


""" transactions/models.py"""


class SupportingDocument(models.Model):
    supporting_docs_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    batchnbr = models.CharField(max_length=6, default='004568')  # Replaces jnldtlref
    entrynbr = models.CharField(max_length=5, default='00001')  # New field
    iddoc = models.CharField(max_length=60, default='EV002703                                                    ')
    fiscal_year = models.CharField(max_length=4)
    fiscal_period = models.CharField(max_length=2)
    supported = models.BooleanField(default=False)
    transaction_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    support_count = models.IntegerField(default=0)  # Number of supporting documents
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = [
            ['project', 'batchnbr', 'entrynbr', 'fiscal_year', 'fiscal_period']
        ]
        indexes = [
            models.Index(fields=['project', 'fiscal_year', 'fiscal_period']),
            models.Index(fields=['supported']),
            models.Index(fields=['batchnbr', 'entrynbr']),  # New composite index
        ]

    def __str__(self):
        return f"{self.project.project_name} - Batch {self.batchnbr}-{self.entrynbr} - FY{self.fiscal_year}P{self.fiscal_period}"


class SupportingDocumentFile(models.Model):
    """
    Store actual document files, linked to BatchSupport
    Multiple documents can support the same batch
    """
    doc_file_id = models.AutoField(primary_key=True)
    batch_support = models.ForeignKey(SupportingDocument, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(
        upload_to='documents/',
        max_length=255,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "jpeg", "png"])]
    )

    document_name = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=50, default='System Upload')
    uploaded_at = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self):
        return f"Document for {self.batch_support}"


class Comments(models.Model):
    comments_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, default=3)
    batchnbr = models.CharField(max_length=6, default='004568')  # Replaces jnldtlref
    entrynbr = models.CharField(max_length=5, default='00002')
    text = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=50, default='System Upload')
    timestamp = models.DateTimeField(auto_now=True)
