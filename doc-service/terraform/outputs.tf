output "s3_bucket_details" {
  description = "Complete S3 bucket details"
  value = {
    name   = aws_s3_bucket.documents.id
    arn    = aws_s3_bucket.documents.arn
    region = aws_s3_bucket.documents.region
  }
}

output "lambda_iam_policy" {
  description = "IAM policy details for Lambda"
  value = {
    arn  = aws_iam_policy.lambda_s3_access.arn
    name = aws_iam_policy.lambda_s3_access.name
  }
}

output "example_usage" {
  description = "Example of how to use the S3 helper in Lambda"
  value = <<-EOT
    const S3DocumentHelper = require('./s3_helpers');
    
    // Initialize helper
    const s3Helper = new S3DocumentHelper('${aws_s3_bucket.documents.id}', '${var.aws_region}');
    
    // Generate signed URL for download (24h expiry)
    const downloadUrl = await s3Helper.getSignedDownloadUrl('path/to/document.pdf');
    
    // Upload a document
    await s3Helper.uploadDocument(
      'client123/2025/01/invoice/invoice-001.pdf',
      pdfBuffer,
      'application/pdf',
      { clientId: 'client123', invoiceNumber: '001' }
    );
  EOT
}